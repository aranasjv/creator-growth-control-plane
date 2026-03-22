import os
import io
import re
import csv
import time
import glob
import shlex
import zipfile
import yagmail
import requests
import subprocess
import platform
from urllib.parse import parse_qs, unquote, urlparse

from cache import *
from status import *
from config import *


class Outreach:
    """
    Class that houses the methods to reach out to businesses.
    """

    def __init__(self) -> None:
        """
        Constructor for the Outreach class.

        Returns:
            None
        """
        # Check if go is installed
        self.go_installed = os.system("go version") == 0

        # Set niche
        self.niche = get_google_maps_scraper_niche()
        self.niches = get_google_maps_scraper_niches()
        self.dry_run = get_outreach_dry_run()

        # Set email credentials
        self.email_creds = get_email_credentials()

    def _get_binary_name(self) -> str:
        return (
            "google-maps-scraper.exe"
            if platform.system() == "Windows"
            else "google-maps-scraper"
        )

    def _scraper_requires_rebuild(self, binary_name: str, scraper_dir: str) -> bool:
        if not scraper_dir or not os.path.exists(binary_name):
            return not os.path.exists(binary_name)

        binary_mtime = os.path.getmtime(binary_name)
        latest_source_mtime = binary_mtime

        for root, _, files in os.walk(scraper_dir):
            for file_name in files:
                if not file_name.endswith((".go", ".mod", ".sum")):
                    continue
                source_path = os.path.join(root, file_name)
                latest_source_mtime = max(latest_source_mtime, os.path.getmtime(source_path))

        return latest_source_mtime > binary_mtime

    def _count_csv_rows(self, file_name: str) -> int:
        if not os.path.exists(file_name):
            return 0

        try:
            with open(file_name, "r", newline="", errors="ignore") as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
        except Exception:
            return 0

        return max(0, len(rows) - 1)

    def _build_scraper_args(self, input_file: str, output_file: str) -> str:
        parts = [
            f'-input "{input_file}"',
            f'-results "{output_file}"',
            f"-depth {get_scraper_depth()}",
            f"-c {get_scraper_concurrency()}",
        ]

        exit_on_inactivity = get_scraper_exit_on_inactivity()
        if exit_on_inactivity:
            parts.append(f"-exit-on-inactivity {exit_on_inactivity}")

        return " ".join(parts)

    def _find_scraper_dir(self) -> str:
        candidates = sorted(glob.glob("google-maps-scraper-*"))
        for candidate in candidates:
            if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, "go.mod")
            ):
                return candidate
        return ""

    def is_go_installed(self) -> bool:
        """
        Check if go is installed.

        Returns:
            bool: True if go is installed, False otherwise.
        """
        # Check if go is installed
        try:
            subprocess.call(["go", "version"])
            return True
        except Exception as e:
            return False

    def unzip_file(self, zip_link: str) -> None:
        """
        Unzip the file.

        Args:
            zip_link (str): The link to the zip file.

        Returns:
            None
        """
        if self._find_scraper_dir():
            info("=> Scraper already unzipped. Skipping unzip.")
            return

        r = requests.get(zip_link)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for member in z.namelist():
            if ".." in member or member.startswith("/"):
                warning(f"Skipping suspicious path in archive: {member}")
                continue
            z.extract(member)

    def build_scraper(self) -> None:
        """
        Build the scraper.

        Returns:
            None
        """
        scraper_dir = self._find_scraper_dir()
        binary_name = self._get_binary_name()

        if os.path.exists(binary_name) and not self._scraper_requires_rebuild(
            binary_name, scraper_dir
        ):
            info("=> Scraper already built. Skipping build.")
            return

        if not scraper_dir:
            raise FileNotFoundError(
                "Could not locate extracted google-maps-scraper directory."
            )

        info("=> Building google-maps-scraper...")
        subprocess.run(["go", "mod", "download"], cwd=scraper_dir, check=True)
        subprocess.run(["go", "build"], cwd=scraper_dir, check=True)

        built_binary = os.path.join(scraper_dir, binary_name)
        if not os.path.exists(built_binary):
            raise FileNotFoundError(f"Expected built scraper binary at: {built_binary}")

        os.replace(built_binary, binary_name)

    def run_scraper_with_args_for_30_seconds(
        self, args: str, output_file: str, timeout=300
    ) -> bool:
        """
        Run the scraper with the specified arguments for 30 seconds.

        Args:
            args (str): The arguments to run the scraper with.
            timeout (int): The time to run the scraper for.

        Returns:
            bool: True when the scraper exits cleanly, otherwise False
        """
        info(" => Running scraper...")
        binary_name = self._get_binary_name()
        command = [os.path.join(os.getcwd(), binary_name)] + shlex.split(args)
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            scraper_process = subprocess.Popen(
                command,
                creationflags=creationflags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = scraper_process.communicate(timeout=float(timeout))

            if scraper_process.returncode == 0:
                success("=> Scraper finished successfully.")
                return True

            row_count = self._count_csv_rows(output_file)
            if row_count > 0:
                warning(
                    f"=> Scraper exited with code {scraper_process.returncode}, but saved {row_count} partial lead(s)."
                )
                return True

            error("=> Scraper finished with an error.")
            if stderr:
                warning(stderr.strip()[:500])
            elif stdout:
                warning(stdout.strip()[:500])
            return False
        except subprocess.TimeoutExpired:
            self.kill_process_tree(scraper_process.pid)
            row_count = self._count_csv_rows(output_file)
            if row_count > 0:
                warning(
                    f"=> Scraper timed out, but saved {row_count} partial lead(s) before shutdown."
                )
                return True

            error("=> Scraper timed out.")
            return False
        except Exception as e:
            error("An error occurred while running the scraper:")
            error(str(e), show_emoji=False)
            return False

    def kill_process_tree(self, pid: int) -> None:
        """
        Kills a scraper process and any children it spawned.

        Args:
            pid (int): Process id to terminate

        Returns:
            None
        """
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                os.kill(pid, 9)
        except Exception:
            pass

    def get_items_from_file(self, file_name: str) -> list[dict]:
        """
        Read and return CSV rows from a file.

        Args:
            file_name (str): The name of the file to read from.

        Returns:
            list[dict]: Parsed rows from the CSV file.
        """
        with open(file_name, "r", newline="", errors="ignore") as csvfile:
            reader = csv.DictReader(csvfile)
            items = []
            for row in reader:
                parsed_row = {
                    str(key).strip(): (value or "").strip()
                    for key, value in row.items()
                    if key is not None
                }

                overflow = row.get(None, [])
                if overflow and "email" not in parsed_row:
                    parsed_row["email"] = overflow[-1].strip()

                items.append(parsed_row)

            return items

    def normalize_website_url(self, website: str) -> str:
        """
        Normalizes a scraped website value into an absolute HTTP(S) URL.

        Args:
            website (str): Raw website value from scraper output

        Returns:
            str: Normalized URL or empty string when invalid
        """
        candidate = (website or "").strip()
        if not candidate:
            return ""

        if candidate.startswith("/url?"):
            parsed = urlparse(candidate)
            query_params = parse_qs(parsed.query)
            target = query_params.get("q", [""])[0].strip()
            candidate = unquote(target) if target else ""

        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate

        return ""

    def _truncate_text(self, value: str, max_length: int = 420) -> str:
        text = (value or "").strip()
        if len(text) <= max_length:
            return text
        return f"{text[:max_length].rstrip()}..."

    def _build_email_preview(self, html_body: str) -> str:
        plain = re.sub(r"<[^>]+>", " ", html_body or "")
        plain = re.sub(r"\s+", " ", plain).strip()
        return self._truncate_text(plain, 420)

    def set_email_for_website(self, index: int, website: str, output_file: str) -> str:
        """Extracts an email address from a website and updates a CSV file with it.

        This method sends a GET request to the specified website, searches for the
        first email address in the HTML content, and appends it to the specified
        row in a CSV file. If no email address is found, no changes are made to
        the CSV file.

        Args:
            index (int): The row index in the CSV file where the email should be appended.
            website (str): The URL of the website to extract the email address from.
            output_file (str): The path to the CSV file to update with the extracted email."""
        # Extract and set an email for a website
        email = ""

        r = requests.get(website, timeout=10)
        if r.status_code == 200:
            email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
            email_addresses = re.findall(email_pattern, r.text)
            email = email_addresses[0] if len(email_addresses) > 0 else ""

        if email:
            info(f"=> Setting email {email} for website {website}")
            with open(output_file, "r", newline="", errors="ignore") as csvfile:
                csvreader = csv.reader(csvfile)
                items = list(csvreader)

            if not items:
                return email

            header = items[0]
            if "email" in header:
                email_index = header.index("email")
            else:
                header.append("email")
                email_index = len(header) - 1

            while len(items[index]) <= email_index:
                items[index].append("")
            items[index][email_index] = email

            with open(output_file, "w", newline="", errors="ignore") as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(items)

        return email

    def start(self) -> dict:
        """
        Start the outreach process.

        Returns:
            dict: Outreach execution summary and email delivery audit info.
        """
        # Check if go is installed
        if not self.is_go_installed():
            raise RuntimeError("Go is not installed. Please install go and try again.")

        # Unzip the scraper
        self.unzip_file(get_google_maps_scraper_zip_url())

        # Build the scraper
        self.build_scraper()

        # Write the niche to a file
        output_path = get_results_cache_path()
        message_subject = get_outreach_message_subject()
        message_body_file = get_outreach_message_body_file()
        results_dir = os.path.join(get_cache_path(), "outreach")
        os.makedirs(results_dir, exist_ok=True)

        niche_outputs = []
        for niche in self.niches or [self.niche]:
            niche_file = "niche.txt"
            with open(niche_file, "w") as f:
                f.write(niche)

            niche_slug = re.sub(r"[^a-z0-9]+", "-", niche.lower()).strip("-") or "niche"
            niche_output = os.path.join(results_dir, f"{niche_slug}.csv")
            if os.path.exists(niche_output):
                os.remove(niche_output)

            info(f" => Scraping niche: {niche}")
            completed = self.run_scraper_with_args_for_30_seconds(
                self._build_scraper_args(niche_file, niche_output),
                niche_output,
                timeout=get_scraper_timeout(),
            )

            if completed and self._count_csv_rows(niche_output) > 0:
                niche_outputs.append((niche, niche_output))
            else:
                warning(
                    f" => Scraper output not found for niche '{niche}' at {niche_output}. Skipping."
                )

        if os.path.exists("niche.txt"):
            os.remove("niche.txt")

        if not niche_outputs:
            raise RuntimeError("No scraper output was produced for any configured niche.")

        self.merge_results([path for _, path in niche_outputs], output_path)

        # Get the items from the file
        items = self.get_items_from_file(output_path)
        success(f" => Scraped {len(items)} items.")

        time.sleep(2)

        if not os.path.exists(message_body_file):
            raise FileNotFoundError(
                f"Outreach body template does not exist: {message_body_file}"
            )

        with open(message_body_file, "r", encoding="utf-8", errors="ignore") as body_file:
            message_body_template = body_file.read()

        max_emails = get_outreach_max_emails()
        emails_prepared = 0
        emails_sent = 0
        emails_failed = 0
        emails_skipped_no_email = 0
        emails_skipped_invalid_website = 0
        cap_reached = False
        email_attempts = []

        smtp_port = int(self.email_creds["smtp_port"])
        smtp_ssl = smtp_port == 465
        smtp_starttls = smtp_port == 587

        yag = None
        if self.dry_run:
            info(" => Outreach dry run is enabled. Emails will not be sent.")
        else:
            # Configure SMTP mode from port so Gmail 587 uses STARTTLS instead of SSL.
            yag = yagmail.SMTP(
                user=self.email_creds["username"],
                password=self.email_creds["password"],
                host=self.email_creds["smtp_server"],
                port=smtp_port,
                smtp_ssl=smtp_ssl,
                smtp_starttls=smtp_starttls,
            )

        # Get the email for each business
        for index, item in enumerate(items, start=1):
            company_name = (item.get("title") or "Business").strip() or "Business"
            website = self.normalize_website_url(item.get("website", ""))

            if website == "":
                emails_skipped_invalid_website += 1
                warning(f" => No website for {company_name}. Skipping email lookup.")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": "",
                        "recipient": "",
                        "status": "skipped_no_website",
                        "subject": "",
                        "bodyPreview": "",
                        "error": "",
                    }
                )
                continue

            try:
                test_r = requests.get(website, timeout=10)
            except Exception as err:
                emails_skipped_invalid_website += 1
                warning(f" => Could not open website {website}. Skipping... ({err})")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": "",
                        "status": "skipped_website_error",
                        "subject": "",
                        "bodyPreview": "",
                        "error": str(err),
                    }
                )
                continue

            if test_r.status_code != 200:
                emails_skipped_invalid_website += 1
                warning(
                    f" => Website {website} returned HTTP {test_r.status_code}. Skipping..."
                )
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": "",
                        "status": "skipped_invalid_website",
                        "subject": "",
                        "bodyPreview": "",
                        "error": f"HTTP {test_r.status_code}",
                    }
                )
                continue

            receiver_email = (item.get("email") or "").strip()
            if "@" not in receiver_email:
                receiver_email = self.set_email_for_website(index, website, output_path)

            if "@" not in receiver_email:
                emails_skipped_no_email += 1
                warning(f" => No email provided for {company_name}. Skipping...")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": "",
                        "status": "skipped_no_email",
                        "subject": "",
                        "bodyPreview": "",
                        "error": "No email found on website.",
                    }
                )
                continue

            if max_emails > 0 and emails_sent >= max_emails:
                cap_reached = True
                warning(
                    f" => Reached live send cap ({max_emails}). Remaining leads will stay unsent."
                )
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": receiver_email,
                        "status": "skipped_cap",
                        "subject": "",
                        "bodyPreview": "",
                        "error": f"Reached configured live send cap ({max_emails}).",
                    }
                )
                break

            subject = message_subject.replace("{{COMPANY_NAME}}", company_name)
            body = message_body_template.replace("{{COMPANY_NAME}}", company_name)
            body_preview = self._build_email_preview(body)
            info(
                f" => Email preview for {receiver_email} | Subject: {subject} | Body: {body_preview}"
            )
            emails_prepared += 1

            if self.dry_run:
                info(f" => Dry run: would send email to {receiver_email}")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": receiver_email,
                        "status": "dry_run",
                        "subject": subject,
                        "bodyPreview": body_preview,
                        "error": "",
                    }
                )
                continue

            try:
                info(f" => Sending email to {receiver_email}...")
                yag.send(
                    to=receiver_email,
                    subject=subject,
                    contents=body,
                )
                emails_sent += 1
                success(f" => Sent email to {receiver_email}")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": receiver_email,
                        "status": "sent",
                        "subject": subject,
                        "bodyPreview": body_preview,
                        "error": "",
                    }
                )
            except Exception as err:
                emails_failed += 1
                error(f" => Email delivery failed for {receiver_email}: {err}")
                email_attempts.append(
                    {
                        "companyName": company_name,
                        "website": website,
                        "recipient": receiver_email,
                        "status": "failed",
                        "subject": subject,
                        "bodyPreview": body_preview,
                        "error": str(err),
                    }
                )

        return {
            "dryRun": self.dry_run,
            "leadsScraped": len(items),
            "emailsPrepared": emails_prepared,
            "emailsSent": emails_sent,
            "emailsFailed": emails_failed,
            "emailsSkippedNoEmail": emails_skipped_no_email,
            "emailsSkippedInvalidWebsite": emails_skipped_invalid_website,
            "emailSendCap": max_emails,
            "emailSendCapReached": cap_reached,
            "emailAttempts": email_attempts[:120],
        }

    def merge_results(self, source_files: list[str], destination_file: str) -> None:
        """
        Merges multiple scraper CSV outputs into a single deduplicated CSV.

        Args:
            source_files (list[str]): CSV files to merge
            destination_file (str): Final merged CSV path

        Returns:
            None
        """
        rows = []
        header = None
        seen = set()

        for source_file in source_files:
            with open(source_file, "r", newline="", errors="ignore") as csvfile:
                reader = csv.reader(csvfile)
                file_rows = list(reader)

            if not file_rows:
                continue

            if header is None:
                header = file_rows[0]

            for row in file_rows[1:]:
                normalized = tuple(cell.strip().lower() for cell in row)
                if normalized in seen:
                    continue
                seen.add(normalized)
                rows.append(row)

        if header is None:
            raise FileNotFoundError("No outreach CSV headers were found to merge.")

        with open(destination_file, "w", newline="", errors="ignore") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            writer.writerows(rows)
