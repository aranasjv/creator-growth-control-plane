import os
import time
from urllib.parse import urlparse
from typing import Any, List

from status import *
from config import *
from constants import *
from utils import prepare_firefox_profile, cleanup_firefox_profile_clone
from llm_provider import generate_text
from .Twitter import Twitter
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager


class AffiliateMarketing:
    """
    This class will be used to handle all the affiliate marketing related operations.
    """

    def __init__(
        self,
        affiliate_link: str,
        fp_profile_path: str,
        twitter_account_uuid: str,
        account_nickname: str,
        topic: str,
    ) -> None:
        """
        Initializes the Affiliate Marketing class.

        Args:
            affiliate_link (str): The affiliate link
            fp_profile_path (str): The path to the Firefox profile
            twitter_account_uuid (str): The Twitter account UUID
            account_nickname (str): The account nickname
            topic (str): The topic of the product

        Returns:
            None
        """
        self._fp_profile_path: str = fp_profile_path

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {fp_profile_path}"
            )

        self._temporary_profile_clone: str | None = None
        runtime_profile_path = fp_profile_path
        try:
            runtime_profile_path, self._temporary_profile_clone = prepare_firefox_profile(
                fp_profile_path
            )
        except Exception as exc:
            warning(
                f"Could not clone Firefox profile for affiliate flow. Falling back to original profile: {exc}"
            )

        # Set the profile path
        self.options.add_argument("-profile")
        self.options.add_argument(runtime_profile_path)

        # Set the service
        self.service: Service = Service(GeckoDriverManager().install())

        # Initialize the browser
        last_error: Exception | None = None
        self.browser: webdriver.Firefox | None = None
        for attempt in range(1, 5):
            try:
                self.browser = webdriver.Firefox(
                    service=self.service, options=self.options
                )
                break
            except Exception as exc:
                last_error = exc
                warning(
                    f"Firefox startup failed for affiliate flow (attempt {attempt}/4): {exc}"
                )
                time.sleep(2)

        if self.browser is None:
            raise RuntimeError(
                f"Could not start Firefox for affiliate flow after retries: {last_error}"
            )

        self.wait: WebDriverWait = WebDriverWait(self.browser, 20)

        # Set the affiliate link
        self.affiliate_link: str = affiliate_link

        parsed_link = urlparse(self.affiliate_link)
        if parsed_link.scheme not in ["http", "https"] or not parsed_link.netloc:
            raise ValueError(
                f"Affiliate link is invalid. Expected a full URL, got: {self.affiliate_link}"
            )

        # Set the Twitter account UUID
        self.account_uuid: str = twitter_account_uuid

        # Set the Twitter account nickname
        self.account_nickname: str = account_nickname

        # Set the Twitter topic
        self.topic: str = topic

        # Scrape the product information
        self.scrape_product_information()

    def _get_first_text(self, selectors: List[tuple[str, str]]) -> str:
        """
        Returns the first non-empty text from any matching element.

        Args:
            selectors (List[tuple[str, str]]): Ordered selector list

        Returns:
            text (str): First non-empty text, or empty string
        """
        for by, value in selectors:
            try:
                elements = self.browser.find_elements(by, value)
            except Exception:
                continue

            for element in elements:
                text = " ".join((element.text or "").split())
                if text:
                    return text

        return ""

    def _get_meta_content(self, selector: str) -> str:
        """
        Returns the first non-empty content attribute for a CSS selector.

        Args:
            selector (str): CSS selector

        Returns:
            content (str): meta content or empty string
        """
        try:
            elements = self.browser.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return ""

        for element in elements:
            value = (element.get_attribute("content") or "").strip()
            if value:
                return value

        return ""

    def _collect_features(self) -> List[str]:
        """
        Collects bullet points from common product page structures.

        Returns:
            features (List[str]): Cleaned feature list
        """
        selectors = [
            (By.ID, AMAZON_FEATURE_BULLETS_ID),
            (By.CSS_SELECTOR, "#feature-bullets li"),
            (By.CSS_SELECTOR, "ul.a-unordered-list li"),
            (By.CSS_SELECTOR, "[data-feature-name='featurebullets'] li"),
            (By.CSS_SELECTOR, "ul li"),
        ]

        features: List[str] = []
        seen: set[str] = set()

        for by, value in selectors:
            try:
                elements = self.browser.find_elements(by, value)
            except Exception:
                continue

            for element in elements:
                text = " ".join((element.text or "").split())
                if len(text) < 4:
                    continue

                lowered = text.lower()
                if lowered in seen:
                    continue

                seen.add(lowered)
                features.append(text)

                if len(features) >= 8:
                    return features

        return features

    def scrape_product_information(self) -> None:
        """
        This method will be used to scrape the product
        information from the affiliate link.
        """
        # Open the affiliate link
        self.browser.get(self.affiliate_link)

        try:
            self.wait.until(
                lambda driver: driver.execute_script("return document.readyState")
                == "complete"
            )
        except Exception:
            pass

        product_title = self._get_first_text(
            [
                (By.ID, AMAZON_PRODUCT_TITLE_ID),
                (By.CSS_SELECTOR, "#productTitle"),
                (By.CSS_SELECTOR, "h1#title span"),
                (By.CSS_SELECTOR, "h1"),
            ]
        )

        if not product_title:
            product_title = self._get_meta_content("meta[property='og:title']")

        if not product_title:
            product_title = self._get_meta_content("meta[name='title']")

        if not product_title:
            page_title = (self.browser.title or "").strip()
            if page_title:
                product_title = page_title.split("|")[0].strip()

        if not product_title:
            parsed_link = urlparse(self.affiliate_link)
            product_title = f"Featured product from {parsed_link.netloc or 'store'}"

        features = self._collect_features()
        if len(features) == 0:
            meta_description = self._get_meta_content("meta[name='description']")
            if meta_description:
                features.append(meta_description)

        if len(features) == 0:
            features.append(f"Related to {self.topic}.")

        if get_verbose():
            info(f"Product Title: {product_title}")

        if get_verbose():
            info(f"Features: {features}")

        # Set the product title
        self.product_title = product_title

        # Set the features
        self.features = features

    def generate_response(self, prompt: str) -> str:
        """
        This method will be used to generate the response for the user.

        Args:
            prompt (str): The prompt for the user.

        Returns:
            response (str): The response for the user.
        """
        return generate_text(prompt)

    def generate_pitch(self) -> str:
        """
        This method will be used to generate a pitch for the product.

        Returns:
            pitch (str): The pitch for the product.
        """
        # Generate the response
        features_summary = "; ".join(self.features[:6]) if isinstance(self.features, list) else str(self.features)
        pitch: str = (
            self.generate_response(
                f'I want to promote this product on my website. Generate a brief pitch about this product, return nothing else except the pitch. Keep it concise for social posting. Information:\nTitle: "{self.product_title}"\nFeatures: "{features_summary}"'
            )
            + "\nYou can buy the product here: "
            + self.affiliate_link
        )

        self.pitch: str = pitch

        # Return the response
        return pitch

    def share_pitch(self, where: str) -> None:
        """
        This method will be used to share the pitch on the specified platform.

        Args:
            where (str): The platform where the pitch will be shared.
        """
        if where == "twitter":
            # Ensure the AFM browser is closed before opening another Firefox
            # instance on the same profile path.
            self.quit()

            payload = " ".join(self.pitch.split())
            if len(payload) > 270:
                payload = payload[:267].rsplit(" ", 1)[0] + "..."

            # Initialize the Twitter class
            twitter: Twitter = Twitter(
                self.account_uuid,
                self.account_nickname,
                self._fp_profile_path,
                self.topic,
            )

            try:
                # Share the pitch
                twitter.post(payload)
            finally:
                try:
                    twitter.browser.quit()
                except Exception:
                    pass

    def quit(self) -> None:
        """
        This method will be used to quit the browser.
        """
        try:
            if self.browser is not None:
                self.browser.quit()
        except Exception:
            pass

        cleanup_firefox_profile_clone(self._temporary_profile_clone)
        self._temporary_profile_clone = None
