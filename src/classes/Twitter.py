import re
import sys
import time
import os
import json

from cache import *
from config import *
from status import *
from utils import prepare_firefox_profile, cleanup_firefox_profile_clone
from llm_provider import generate_text, get_managed_prompt
from typing import List, Optional
from datetime import datetime
from termcolor import colored
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Twitter:
    """
    Class for the Bot, that grows a Twitter account.
    """

    def __init__(
        self, account_uuid: str, account_nickname: str, fp_profile_path: str, topic: str
    ) -> None:
        """
        Initializes the Twitter Bot.

        Args:
            account_uuid (str): The account UUID
            account_nickname (str): The account nickname
            fp_profile_path (str): The path to the Firefox profile

        Returns:
            None
        """
        self.account_uuid: str = account_uuid
        self.account_nickname: str = account_nickname
        self.fp_profile_path: str = fp_profile_path
        self.topic: str = topic

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
            warning(f"Could not clone Firefox profile for Twitter. Falling back to original profile: {exc}")

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
                    f"Firefox startup failed for Twitter (attempt {attempt}/4): {exc}"
                )
                time.sleep(2)

        if self.browser is None:
            raise RuntimeError(
                f"Could not start Firefox for Twitter after retries: {last_error}"
            )

        self.wait: WebDriverWait = WebDriverWait(self.browser, 30)

    def post(self, text: Optional[str] = None) -> None:
        """
        Starts the Twitter Bot.

        Args:
            text (str): The text to post

        Returns:
            None
        """
        bot: webdriver.Firefox = self.browser
        verbose: bool = get_verbose()

        bot.get("https://x.com/compose/post")

        post_content: str = text if text is not None else self.generate_post()
        now: datetime = datetime.now()

        print(colored(" => Posting to Twitter:", "blue"), post_content[:30] + "...")
        body = post_content

        text_box = None
        text_box_selectors = [
            (By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0'][role='textbox']"),
            (By.XPATH, "//div[@data-testid='tweetTextarea_0']//div[@role='textbox']"),
            (By.XPATH, "//div[@role='textbox']"),
        ]

        for selector in text_box_selectors:
            try:
                text_box = self.wait.until(EC.element_to_be_clickable(selector))
                text_box.click()
                text_box.send_keys(body)
                break
            except Exception:
                continue

        if text_box is None:
            raise RuntimeError(
                "Could not find tweet text box. Ensure you are logged into X in this Firefox profile."
            )


        post_button = None
        post_button_selectors = [
            (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
            (By.XPATH, "//button[@data-testid='tweetButton']"),
            (By.XPATH, "//span[text()='Post']/ancestor::button"),
        ]

        for selector in post_button_selectors:
            try:
                post_button = self.wait.until(EC.element_to_be_clickable(selector))
                post_button.click()
                break
            except Exception:
                continue

        if post_button is None:
            raise RuntimeError("Could not find the Post button on X compose screen.")

        if verbose:
            print(colored(" => Pressed [ENTER] Button on Twitter..", "blue"))
        time.sleep(2)

        # Add the post to the cache
        self.add_post({"content": body, "date": now.strftime("%m/%d/%Y, %H:%M:%S")})

        success("Posted to Twitter successfully!")

    def get_posts(self) -> List[dict]:
        """
        Gets the posts from the cache.

        Returns:
            posts (List[dict]): The posts
        """
        if not os.path.exists(get_twitter_cache_path()):
            # Create the cache file
            with open(get_twitter_cache_path(), "w") as file:
                json.dump({"accounts": []}, file, indent=4)

        with open(get_twitter_cache_path(), "r") as file:
            parsed = json.load(file)

            # Find our account
            accounts = parsed["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    posts = account["posts"]

                    if posts is None:
                        return []

                    # Return the posts
                    return posts

        return []

    def add_post(self, post: dict) -> None:
        """
        Adds a post to the cache.

        Args:
            post (dict): The post to add

        Returns:
            None
        """
        posts = self.get_posts()
        posts.append(post)

        with open(get_twitter_cache_path(), "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    account["posts"].append(post)

            # Commit changes
            with open(get_twitter_cache_path(), "w") as f:
                f.write(json.dumps(previous_json))

    def generate_post(self) -> str:
        """
        Generates a post for the Twitter account based on the topic.

        Returns:
            post (str): The post
        """
        completion = generate_text(
            prompt=get_managed_prompt(
                "twitter_post_generation",
                "Generate a highly engaging, native X post about {topic}.",
                topic=self.topic
            )
        )

        if get_verbose():
            info("Generating a post...")

        if completion is None:
            error("Failed to generate a post. Please try again.")
            sys.exit(1)

        # Apply Regex to remove all *
        completion = re.sub(r"\*", "", completion).replace('"', "")

        if get_verbose():
            info(f"Length of post: {len(completion)}")
        if len(completion) >= 260:
            return completion[:257].rsplit(" ", 1)[0] + "..."

        return completion

    def quit(self) -> None:
        """
        Closes browser resources and cleans up temporary profile clones.

        Returns:
            None
        """
        try:
            if self.browser is not None:
                self.browser.quit()
        except Exception:
            pass

        cleanup_firefox_profile_clone(self._temporary_profile_clone)
        self._temporary_profile_clone = None
