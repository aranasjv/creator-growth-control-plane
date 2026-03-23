import re
import base64
import json
import time
import os
import threading
import traceback
import textwrap
import requests
import assemblyai as aai

from utils import *
from cache import *
from .Tts import TTS
from llm_provider import generate_text
from config import *
from status import *
from uuid import uuid4
from constants import *
from typing import Any, List
from moviepy.editor import *
from termcolor import colored
from selenium import webdriver
from moviepy.video.fx.all import crop
from moviepy.config import change_settings
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from moviepy.video.tools.subtitles import SubtitlesClip
from webdriver_manager.firefox import GeckoDriverManager
from datetime import datetime
from PIL import Image, ImageDraw
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import fal_client
except Exception:
    fal_client = None

try:
    from google import genai as google_genai_client
    from google.genai import types as google_genai_types
except Exception:
    google_genai_client = None
    google_genai_types = None

# Set ImageMagick Path
change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})


class YouTube:
    """
    Class for YouTube Automation.

    Steps to create a YouTube Short:
    1. Generate a topic [DONE]
    2. Generate a script [DONE]
    3. Generate metadata (Title, Description, Tags) [DONE]
    4. Generate AI Image Prompts [DONE]
    4. Generate Images based on generated Prompts [DONE]
    5. Convert Text-to-Speech [DONE]
    6. Show images each for n seconds, n: Duration of TTS / Amount of images [DONE]
    7. Combine Concatenated Images with the Text-to-Speech [DONE]
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
        forced_topic: str | None = None,
        allow_topic_generation: bool = False,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the firefox profile that is logged into the specificed YouTube Account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        self._language: str = language
        self._forced_topic: str = str(forced_topic or "").strip()
        self._allow_topic_generation: bool = bool(allow_topic_generation)

        self.images = []
        self.motion_clips: List[str | None] = []
        self._fal_readiness_warning_emitted = False

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(self._fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {self._fp_profile_path}"
            )

        self._temporary_profile_clone: str | None = None
        runtime_profile_path = self._fp_profile_path
        try:
            runtime_profile_path, self._temporary_profile_clone = prepare_firefox_profile(
                self._fp_profile_path
            )
        except Exception as exc:
            warning(
                f"Could not clone Firefox profile for YouTube. Falling back to original profile: {exc}"
            )

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
                    f"Firefox startup failed for YouTube (attempt {attempt}/4): {exc}"
                )
                time.sleep(2)

        if self.browser is None:
            raise RuntimeError(
                f"Could not start Firefox for YouTube after retries: {last_error}"
            )

        self.last_upload_error: str | None = None

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche

    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_response(self, prompt: str, model_name: str = None) -> str:
        """
        Generates an LLM Response based on a prompt and the user-provided model.

        Args:
            prompt (str): The prompt to use in the text generation.

        Returns:
            response (str): The generated AI Repsonse.
        """
        return generate_text(prompt, model_name=model_name)

    def _clean_text_response(self, value: str) -> str:
        cleaned = str(value or "")
        cleaned = cleaned.replace("```json", "").replace("```", "")
        cleaned = re.sub(r"^\s*(script|caption|output)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _estimate_script_duration_seconds(self, script: str) -> float:
        words = re.findall(r"[A-Za-z0-9À-ÿ']+", str(script or ""))
        if not words:
            return 0.0
        # ~145 wpm is a practical narration pace for shorts.
        return (len(words) / 145.0) * 60.0

    def _is_filipino_dominant(self, text: str) -> bool:
        sample = str(text or "").lower()
        tokens = re.findall(r"[a-zA-ZÀ-ÿ']+", sample)
        if not tokens:
            return False

        filipino_markers = {
            "ang", "mga", "naman", "kasi", "po", "opo", "hindi", "paano", "ikaw",
            "ako", "tayo", "sila", "ng", "sa", "para", "at", "pero", "kayo",
            "salamat", "kamusta", "gusto", "dito", "doon", "kapag", "lang", "ito",
            "iyan", "yan", "nito", "natin", "amin", "nila", "maaaring", "dapat",
        }
        english_markers = {
            "the", "and", "this", "that", "with", "for", "you", "your", "are",
            "is", "to", "from", "how", "why", "what", "when", "where", "can",
            "will", "business", "marketing", "video", "content", "growth",
        }

        filipino_hits = sum(1 for token in tokens if token in filipino_markers)
        english_hits = sum(1 for token in tokens if token in english_markers)

        if filipino_hits == 0 and english_hits > 1:
            return False

        return filipino_hits >= english_hits

    def _truncate_script_words(self, script: str, max_words: int) -> str:
        words = re.findall(r"[A-Za-z0-9À-ÿ']+", str(script or ""))
        if not words:
            return ""
        if len(words) <= max_words:
            return " ".join(words).strip()
        return (" ".join(words[:max_words]).strip() + ".").strip()

    def _enforce_script_constraints(self, script: str) -> str:
        max_seconds = get_youtube_max_short_duration_seconds()
        max_words = max(40, int(max_seconds * 2.2))
        language_requirement = get_youtube_script_language() or self.language or "Filipino"
        requires_filipino = language_requirement.strip().lower() in {"filipino", "tagalog", "fil"}

        candidate = self._clean_text_response(script)

        def is_compliant(value: str) -> bool:
            if not value:
                return False
            if self._estimate_script_duration_seconds(value) > (max_seconds + 2):
                return False
            if requires_filipino and not self._is_filipino_dominant(value):
                return False
            return True

        if is_compliant(candidate):
            return candidate

        from llm_provider import get_managed_prompt

        for _ in range(2):
            rewrite_prompt = get_managed_prompt(
                "youtube_script_rewrite_constraints",
                default_prompt=(
                    "Rewrite this short-video script so it is fully compliant.\n"
                    "Topic: {subject}\n"
                    "Required language: {language_requirement}\n"
                    "Maximum duration: {max_seconds} seconds\n"
                    "Maximum words: {max_words}\n"
                    "Rules:\n"
                    "1) Keep the same topic and meaning.\n"
                    "2) Use Filipino only. Do not mix English except unavoidable proper nouns.\n"
                    "3) Keep it natural and conversational.\n"
                    "4) Return plain script text only.\n\n"
                    "Script:\n{script}"
                ),
                subject=self.subject,
                language_requirement=language_requirement,
                max_seconds=max_seconds,
                max_words=max_words,
                script=candidate,
            )
            rewritten = self._clean_text_response(self.generate_response(rewrite_prompt))
            if rewritten:
                candidate = rewritten
            if is_compliant(candidate):
                return candidate

        candidate = self._truncate_script_words(candidate, max_words=max_words)

        if requires_filipino and not self._is_filipino_dominant(candidate):
            fallback_subject = re.sub(r"[^\w\s-]", "", str(self.subject or "")).strip() or "paksa"
            candidate = (
                f"Pag-uusapan natin ngayon ang {fallback_subject}. "
                "Narito ang malinaw at praktikal na paliwanag para agad mong magamit. "
                "Gawin mo ang mga simpleng hakbang na ito para mas mabilis ang resulta."
            )

        return self._truncate_script_words(candidate, max_words=max_words)

    def generate_topic(self) -> str:
        """
        Generates a topic based on the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        # By default we lock topic to account config so script, visuals, and
        # metadata stay aligned. Dynamic topic expansion is opt-in.
        if self._forced_topic and not self._allow_topic_generation:
            self.subject = self._forced_topic
            return self.subject

        from llm_provider import get_managed_prompt
        prompt_text = get_managed_prompt(
            "youtube_topic_generation",
            default_prompt=(
                "Generate one specific short-video idea strictly inside this topic: {niche}. "
                "Do not change domain, audience, or intent. Return one sentence only."
            ),
            niche=self._forced_topic or self.niche
        )
        completion = str(self.generate_response(prompt_text) or "").strip()

        if not completion:
            warning("Topic generation returned empty response. Using configured topic seed.")
            completion = self._forced_topic or self.niche

        self.subject = completion

        return completion

    def generate_script(self, longform_content: str = None) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        max_short_seconds = get_youtube_max_short_duration_seconds()
        target_max_words = max(40, int(max_short_seconds * 2.2))
        script_language = get_youtube_script_language() or self.language or "Filipino"
        from llm_provider import get_managed_prompt
        
        if longform_content:
            prompt_text = get_managed_prompt(
                "short_from_longform_script",
                default_prompt=(
                    "Create a {sentence_length}-sentence short-form script strictly about this topic: {subject}. "
                    "Use the long-form content only as supporting material. "
                    "If any part of the content is off-topic, ignore it. "
                    "The final script must remain fully on-topic for {subject}. "
                    "Language must be {script_language}. "
                    "Use Filipino only, no English except unavoidable proper nouns. "
                    "Keep total duration under {max_short_seconds} seconds and under {target_max_words} words. "
                    "No formatting, no labels, return script text only.\n\n"
                    "Content:\n{content}"
                ),
                sentence_length=sentence_length,
                subject=self.subject,
                content=longform_content,
                script_language=script_language,
                max_short_seconds=max_short_seconds,
                target_max_words=target_max_words,
            )
        else:
            prompt_text = get_managed_prompt(
                "youtube_script_generation",
                default_prompt=(
                    "Generate a {sentence_length}-sentence vertical short script in {script_language}, "
                    "strictly about: {subject}. Keep every sentence tied to the same topic. "
                    "Use Filipino only, no English except unavoidable proper nouns. "
                    "Keep it under {max_short_seconds} seconds and under {target_max_words} words. "
                    "Return script text only."
                ),
                sentence_length=sentence_length,
                subject=self.subject,
                script_language=script_language,
                max_short_seconds=max_short_seconds,
                target_max_words=target_max_words,
            )

        completion = self._clean_text_response(self.generate_response(prompt_text) or "")

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            completion = f"{self.subject}. {self.subject}. {self.subject}."

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script(longform_content=longform_content)

        completion = self._enforce_script_constraints(completion).strip()
        self.script = completion

        return self.script

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description).

        Returns:
            metadata (dict): The generated metadata.
        """
        from llm_provider import get_managed_prompt
        script_language = get_youtube_script_language() or self.language or "Filipino"
        title_prompt = get_managed_prompt(
            "youtube_metadata_title",
            default_prompt=(
                "Write one YouTube Shorts title under 100 characters for this topic: {subject}. "
                "Must match the script context and avoid unrelated topics. "
                "Language must be {script_language}. Return title only."
            ),
            subject=self.subject,
            script_language=script_language,
        )
        title = str(self.generate_response(title_prompt) or "").strip()

        if not title:
            title = str(self.subject or "Short video").strip()[:100]

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        desc_prompt = get_managed_prompt(
            "youtube_metadata_description",
            default_prompt=(
                "Write a concise YouTube Shorts description based on this script and topic.\n"
                "Topic: {subject}\nScript: {script}\n"
                "Language must be {script_language}. Must stay on-topic. Return description only."
            ),
            subject=self.subject,
            script=self.script,
            script_language=script_language,
        )
        description = str(self.generate_response(desc_prompt) or "").strip()
        if not description:
            description = f"{self.subject}\n\n#shorts"

        self.metadata = {"title": title, "description": description}

        return self.metadata

    def generate_prompts(self) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        # Bound prompt count to avoid runaway image generation when the model
        # returns a long script block.
        sentence_candidates = [
            chunk.strip()
            for chunk in re.split(r"[.!?]+", str(self.script))
            if chunk and chunk.strip()
        ]
        estimated_from_sentences = max(4, len(sentence_candidates))
        max_prompt_count = get_youtube_image_prompt_max_count()
        n_prompts = max(1, min(max_prompt_count, estimated_from_sentences))

        from llm_provider import get_managed_prompt
        prompt_text = get_managed_prompt(
            "youtube_image_prompts",
            default_prompt=(
                "Generate exactly {n_prompts} image prompts as a JSON array of strings.\n"
                "Topic anchor (must be present in every prompt): {subject}\n"
                "Script context:\n{script}\n"
                "Rules:\n"
                "1) Stay strictly on topic anchor.\n"
                "2) Do not introduce unrelated people/brands/events.\n"
                "3) Align each prompt with script progression.\n"
                "4) No text overlays.\n"
                "Return JSON array only."
            ),
            n_prompts=n_prompts,
            subject=self.subject,
            script=self.script
        )

        completion = (
            str(self.generate_response(prompt_text))
            .replace("```json", "")
            .replace("```", "")
        )

        image_prompts = []

        if "image_prompts" in completion:
            parsed = json.loads(completion)
            image_prompts = parsed.get("image_prompts", []) if isinstance(parsed, dict) else []
        else:
            try:
                image_prompts = json.loads(completion)
                if get_verbose():
                    info(f" => Generated Image Prompts: {image_prompts}")
            except Exception:
                if get_verbose():
                    warning(
                        "LLM returned an unformatted response. Attempting to clean..."
                    )

                # Extract a JSON-like array from the response body.
                match = re.search(r"\[[\s\S]*\]", completion)
                if match:
                    try:
                        image_prompts = json.loads(match.group(0))
                    except Exception:
                        image_prompts = []

                if len(image_prompts) == 0:
                    if get_verbose():
                        warning("Failed to generate Image Prompts. Retrying...")
                    return self.generate_prompts()

        if not isinstance(image_prompts, list):
            image_prompts = []

        image_prompts = [
            str(item).strip()
            for item in image_prompts
            if str(item).strip()
        ]

        if len(image_prompts) > n_prompts:
            image_prompts = image_prompts[:n_prompts]

        self.image_prompts = image_prompts

        success(f"Generated {len(image_prompts)} Image Prompts.")

        return image_prompts

    def _enhance_visual_prompt(self, prompt: str) -> str:
        """
        Appends a stable visual style directive to keep generated shots
        closer to high-retention short-form aesthetics.

        Args:
            prompt (str): Base prompt generated from script context

        Returns:
            enhanced_prompt (str): Prompt with style constraints
        """
        style_directive = (
            "Vertical 9:16 UGC framing, handheld-phone realism, expressive 3D animated subject, "
            "cinematic close-up, high detail, dramatic soft lighting, shallow depth of field, "
            "tactile textures, high contrast, emotional framing, no text overlay, no watermark."
        )
        base = str(prompt or "").strip()
        if not base:
            return style_directive
        return f"{base}. {style_directive}"

    def _persist_image(self, image_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated image bytes to a PNG file in .mp.

        Args:
            image_bytes (bytes): Image payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute image path
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        if get_verbose():
            info(f' => Wrote image from {provider_label} to "{image_path}"')

        self.images.append(image_path)
        return image_path

    def _persist_video(self, video_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated video bytes to an MP4 file in .mp.

        Args:
            video_bytes (bytes): Video payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute video path
        """
        video_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")

        with open(video_path, "wb") as video_file:
            video_file.write(video_bytes)

        if get_verbose():
            info(f' => Wrote video from {provider_label} to "{video_path}"')

        return video_path

    def _write_video_file_with_growth_guard(
        self,
        output_path: str,
        writer: Any,
        provider_label: str,
    ) -> str:
        """
        Runs a blocking writer while monitoring local file growth.

        Args:
            output_path (str): Target output file path
            writer (Any): Callable that writes to output_path
            provider_label (str): Provider label for logs/errors

        Returns:
            path (str): Output path after successful write
        """
        state = {"done": False, "error": None}

        def _run_writer() -> None:
            try:
                writer(output_path)
            except Exception as exc:
                state["error"] = exc
            finally:
                state["done"] = True

        thread = threading.Thread(target=_run_writer, daemon=True)
        thread.start()

        stall_timeout = get_video_download_stall_timeout_seconds()
        overall_timeout = get_gemini_veo_download_timeout_seconds()
        last_growth = time.time()
        last_size = -1
        deadline = time.time() + overall_timeout

        while thread.is_alive():
            if time.time() > deadline:
                raise TimeoutError(f"{provider_label} write exceeded {overall_timeout} seconds.")

            current_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            if current_size > last_size:
                last_size = current_size
                last_growth = time.time()
            elif time.time() - last_growth > stall_timeout:
                raise TimeoutError(
                    f"{provider_label} write stalled: file size did not change for {stall_timeout} seconds."
                )

            time.sleep(5)

        thread.join(timeout=1)

        if state["error"] is not None:
            raise RuntimeError(f"{provider_label} write failed: {state['error']}") from state["error"]

        final_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        if final_size <= 0:
            raise RuntimeError(f"{provider_label} write completed but produced an empty file.")

        if get_verbose():
            info(f' => Wrote video from {provider_label} to "{output_path}" ({final_size} bytes)')

        return output_path

    def _download_video_with_growth_guard(
        self,
        url: str,
        provider_label: str,
        headers: dict[str, str] | None = None,
    ) -> str | None:
        """
        Downloads a large video file while enforcing growth-stall timeout.

        Args:
            url (str): Remote file URL
            provider_label (str): Provider label

        Returns:
            path (str | None): Saved local path
        """
        output_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")

        def _writer(target_path: str) -> None:
            with requests.get(
                url,
                timeout=(20, 60),
                stream=True,
                allow_redirects=True,
                headers=headers,
            ) as response:
                response.raise_for_status()
                with open(target_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 512):
                        if not chunk:
                            continue
                        file.write(chunk)

        try:
            return self._write_video_file_with_growth_guard(output_path, _writer, provider_label)
        except Exception as exc:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            if get_verbose():
                warning(f"Could not download video from {provider_label}: {exc}")
            return None

    def _is_hq_mode(self) -> bool:
        mode = str(get_video_quality_mode() or "").strip().lower()
        return mode in {"hq", "hq_hybrid", "fal", "fal_hq"}

    def _fal_ready(self) -> bool:
        if not self._is_hq_mode():
            return False
        if fal_client is None:
            if get_verbose() and not self._fal_readiness_warning_emitted:
                warning("fal-client is not installed. Falling back to standard render pipeline.")
                self._fal_readiness_warning_emitted = True
            return False
        if not get_fal_api_key():
            if get_verbose() and not self._fal_readiness_warning_emitted:
                warning("FAL_KEY/fal_api_key is not configured. Falling back to standard render pipeline.")
                self._fal_readiness_warning_emitted = True
            return False
        return True

    def _run_fal_request(self, model: str, arguments: dict) -> dict | None:
        """
        Executes a fal model request with subscribe first, then run fallback.

        Args:
            model (str): fal model id
            arguments (dict): Input args

        Returns:
            result (dict | None): Model result payload
        """
        if not self._fal_ready():
            return None

        os.environ["FAL_KEY"] = get_fal_api_key()

        timeout = get_fal_client_timeout()
        try:
            # subscribe handles queue/update semantics for long running models.
            return fal_client.subscribe(
                model,
                arguments=arguments,
                client_timeout=timeout,
            )
        except TypeError:
            # Some fal-client versions do not expose timeout in subscribe.
            try:
                return fal_client.subscribe(model, arguments=arguments)
            except Exception as exc:
                if get_verbose():
                    warning(f"fal subscribe failed for {model}: {exc}")
        except Exception as exc:
            if get_verbose():
                warning(f"fal subscribe failed for {model}, trying run(): {exc}")

        try:
            return fal_client.run(model, arguments=arguments)
        except Exception as exc:
            if get_verbose():
                warning(f"fal run failed for {model}: {exc}")
            return None

    def _extract_media_url(self, payload: Any, media_kind: str) -> str | None:
        """
        Extracts image/video URL from fal payload variants.

        Args:
            payload (Any): Response payload
            media_kind (str): 'image' or 'video'

        Returns:
            url (str | None): Media URL
        """
        if payload is None:
            return None

        if hasattr(payload, "data"):
            payload = payload.data

        if not isinstance(payload, dict):
            return None

        candidates: List[str | None] = []
        if media_kind == "image":
            images = payload.get("images")
            if isinstance(images, list):
                for item in images:
                    if isinstance(item, dict):
                        candidates.append(str(item.get("url") or "").strip())
                    elif isinstance(item, str):
                        candidates.append(item.strip())
            image_obj = payload.get("image")
            if isinstance(image_obj, dict):
                candidates.append(str(image_obj.get("url") or "").strip())
            candidates.append(str(payload.get("image_url") or "").strip())
            candidates.append(str(payload.get("url") or "").strip())
        else:
            video_obj = payload.get("video")
            if isinstance(video_obj, dict):
                candidates.append(str(video_obj.get("url") or "").strip())
            videos = payload.get("videos")
            if isinstance(videos, list):
                for item in videos:
                    if isinstance(item, dict):
                        candidates.append(str(item.get("url") or "").strip())
                    elif isinstance(item, str):
                        candidates.append(item.strip())
            candidates.append(str(payload.get("video_url") or "").strip())
            candidates.append(str(payload.get("url") or "").strip())

        for candidate in candidates:
            if candidate and candidate.startswith("http"):
                return candidate
        return None

    def _download_binary(self, url: str, timeout: int = 300) -> bytes | None:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            if get_verbose():
                warning(f"Failed downloading media from {url}: {exc}")
            return None

    def generate_image_nanobanana2(self, prompt: str) -> str:
        """
        Generates an AI Image using Nano Banana 2 API (Gemini image API).

        Args:
            prompt (str): Prompt for image generation

        Returns:
            path (str): The path to the generated image.
        """
        print(f"Generating Image using Nano Banana 2 API: {prompt}")

        api_key = get_nanobanana2_api_key()
        if not api_key:
            error("nanobanana2_api_key is not configured.")
            return None

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        aspect_ratio = get_nanobanana2_aspect_ratio()

        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        last_error = None
        for attempt in range(1, 3):
            try:
                response = requests.post(
                    endpoint,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                    # Separate connect/read timeout keeps jobs from hanging on a single prompt.
                    timeout=(20, get_nanobanana2_timeout_seconds()),
                )
                response.raise_for_status()
                body = response.json()

                candidates = body.get("candidates", [])
                for candidate in candidates:
                    content = candidate.get("content", {})
                    for part in content.get("parts", []):
                        inline_data = part.get("inlineData") or part.get("inline_data")
                        if not inline_data:
                            continue
                        data = inline_data.get("data")
                        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                        if data and str(mime_type).startswith("image/"):
                            image_bytes = base64.b64decode(data)
                            return self._persist_image(image_bytes, "Nano Banana 2 API")

                if get_verbose():
                    warning(f"Nano Banana 2 did not return an image payload. Response: {body}")
                return None
            except Exception as e:
                last_error = e
                if get_verbose():
                    warning(f"Failed Nano Banana 2 attempt {attempt}/2: {str(e)}")
                time.sleep(1.5)

        if get_verbose() and last_error is not None:
            warning(f"Nano Banana 2 failed after retries: {last_error}")
        return None

    def generate_image_fal_nanobanana_pro(self, prompt: str) -> str | None:
        """
        Generates an image through fal.ai Nano Banana Pro.

        Args:
            prompt (str): Prompt for image generation

        Returns:
            path (str | None): Image path when successful
        """
        arguments = {
            "prompt": prompt,
            "image_size": get_fal_image_size(),
            "num_images": 1,
        }
        payload = self._run_fal_request(get_fal_image_model(), arguments)
        if payload is None:
            return None
        image_url = self._extract_media_url(payload, "image")
        if not image_url:
            if get_verbose():
                warning(f"fal image model returned no image URL. Payload: {payload}")
            return None

        image_bytes = self._download_binary(image_url)
        if not image_bytes:
            return None
        return self._persist_image(image_bytes, "fal Nano Banana Pro")

    def generate_motion_clip_veo3(self, prompt: str, image_path: str) -> str | None:
        """
        Generates a short motion clip from an image using Veo 3 image-to-video.

        Args:
            prompt (str): Animation prompt
            image_path (str): Local input image path

        Returns:
            path (str | None): Motion clip path
        """
        if not get_fal_enable_veo_motion():
            return None
        if not self._fal_ready():
            return None

        try:
            image_url = fal_client.upload_file(image_path)
        except Exception as exc:
            if get_verbose():
                warning(f"fal upload_file failed for Veo 3 input image: {exc}")
            return None

        motion_prompt = (
            f"{prompt}. Vertical 9:16 UGC social video movement, "
            "natural handheld camera sway, subtle parallax, expressive character motion, "
            "high visual fidelity, no text, no subtitles, no watermark."
        )
        arguments = {
            "prompt": motion_prompt,
            "image_url": image_url,
            "aspect_ratio": "9:16",
            "duration": get_fal_veo_duration(),
            "resolution": get_fal_veo_resolution(),
            "generate_audio": get_fal_veo_generate_audio(),
        }

        payload = self._run_fal_request(get_fal_veo_model(), arguments)
        video_url = self._extract_media_url(payload, "video")
        if not video_url:
            if get_verbose():
                warning(f"Veo request returned no video URL. Payload: {payload}")
            return None

        return self._download_video_with_growth_guard(video_url, "fal Veo 3")

    def _guess_mime_type(self, path: str) -> str:
        lowered = str(path or "").lower()
        if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
            return "image/jpeg"
        if lowered.endswith(".webp"):
            return "image/webp"
        return "image/png"

    def _extract_gemini_video_uri(self, operation_payload: dict) -> str | None:
        """
        Extracts generated video URI from a Gemini Veo operation payload.

        Args:
            operation_payload (dict): Poll response payload

        Returns:
            uri (str | None): Download URI
        """
        if not isinstance(operation_payload, dict):
            return None

        response = operation_payload.get("response") or {}

        # REST examples expose generateVideoResponse.generatedSamples[0].video.uri
        generated_samples = (
            response.get("generateVideoResponse", {})
            .get("generatedSamples", [])
        )
        if isinstance(generated_samples, list) and generated_samples:
            sample_video = generated_samples[0].get("video", {})
            uri = str(sample_video.get("uri") or "").strip()
            if uri:
                return uri

        # SDK-style shape fallback.
        generated_videos = response.get("generatedVideos", [])
        if isinstance(generated_videos, list) and generated_videos:
            video_obj = generated_videos[0].get("video", {})
            uri = str(video_obj.get("uri") or "").strip()
            if uri:
                return uri

        return None

    def generate_motion_clip_gemini_veo31(self, prompt: str, image_path: str) -> str | None:
        """
        Generates image-to-video motion clip via Google AI Studio / Gemini Veo 3.1.

        Args:
            prompt (str): Animation prompt
            image_path (str): Local image path used as first frame

        Returns:
            path (str | None): Motion clip path
        """
        if not get_fal_enable_veo_motion():
            return None

        api_key = get_nanobanana2_api_key()
        if not api_key:
            if get_verbose():
                warning("Gemini API key is not configured; cannot run Veo 3.1 motion.")
            return None

        if not os.path.exists(image_path):
            return None

        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
        except Exception as exc:
            if get_verbose():
                warning(f"Could not read image for Veo 3.1: {exc}")
            return None

        motion_prompt = (
            f"{prompt}. Keep the exact same subject and topic context. "
            "Vertical 9:16 short-form social shot, natural handheld camera movement, "
            "subtle depth/parallax, smooth realistic motion, no text or captions in the image."
        )

        model_candidates = [str(get_gemini_veo_model() or "").strip(), "veo-3.1-fast-generate-preview"]
        deduped_models = []
        seen_models = set()
        for item in model_candidates:
            if item and item not in seen_models:
                seen_models.add(item)
                deduped_models.append(item)

        # Preferred path: official google-genai SDK for AI Studio keys.
        if google_genai_client is not None and google_genai_types is not None:
            try:
                client = google_genai_client.Client(api_key=api_key)
                image_obj = google_genai_types.Image(
                    image_bytes=image_bytes,
                    mime_type=self._guess_mime_type(image_path),
                )
            except Exception as exc:
                if get_verbose():
                    warning(f"Could not initialize google-genai Veo client: {exc}")
                client = None

            if client is not None:
                for model in deduped_models:
                    try:
                        operation = client.models.generate_videos(
                            model=model,
                            prompt=motion_prompt,
                            image=image_obj,
                            config=google_genai_types.GenerateVideosConfig(
                                number_of_videos=1,
                                aspect_ratio=get_gemini_veo_aspect_ratio(),
                                duration_seconds=str(get_gemini_veo_duration_seconds()),
                                resolution=get_gemini_veo_resolution(),
                                person_generation="allow_adult",
                            ),
                        )

                        poll_deadline = time.time() + get_gemini_veo_timeout_seconds()
                        poll_interval = get_gemini_veo_poll_interval_seconds()

                        while not bool(getattr(operation, "done", False)):
                            if time.time() >= poll_deadline:
                                raise TimeoutError("Gemini Veo operation timed out before completion.")
                            time.sleep(poll_interval)
                            operation = client.operations.get(operation)

                        op_error = getattr(operation, "error", None)
                        if op_error:
                            raise RuntimeError(f"Gemini Veo operation error: {op_error}")

                        response = getattr(operation, "response", None)
                        generated_videos = getattr(response, "generated_videos", None) or []
                        if not generated_videos:
                            raise RuntimeError("Gemini Veo completed without generated videos.")

                        generated_video = generated_videos[0].video
                        output_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")

                        # Ensure bytes are present before save().
                        try:
                            client.files.download(file=generated_video)
                        except Exception:
                            pass

                        if hasattr(generated_video, "save"):
                            def _sdk_writer(target_path: str) -> None:
                                generated_video.save(target_path)

                            return self._write_video_file_with_growth_guard(
                                output_path,
                                _sdk_writer,
                                "Gemini Veo 3.1 SDK",
                            )

                        video_bytes = getattr(generated_video, "video_bytes", None)
                        if video_bytes:
                            with open(output_path, "wb") as file:
                                file.write(video_bytes)
                            return output_path

                        raise RuntimeError("Gemini Veo returned video object without downloadable bytes.")
                    except Exception as exc:
                        if get_verbose():
                            warning(f"Gemini Veo SDK request failed for model {model}: {exc}")

        # Fallback path: direct REST (kept for compatibility).
        base_url = get_nanobanana2_api_base_url().rstrip("/")
        payload = {
            "instances": [
                {
                    "prompt": motion_prompt,
                    "image": {
                        "inlineData": {
                            "mimeType": self._guess_mime_type(image_path),
                            "data": base64.b64encode(image_bytes).decode("utf-8"),
                        }
                    },
                }
            ],
            "parameters": {
                "numberOfVideos": 1,
                "aspectRatio": get_gemini_veo_aspect_ratio(),
                "durationSeconds": str(get_gemini_veo_duration_seconds()),
                "resolution": get_gemini_veo_resolution(),
                # Veo 3.1 requires allow_adult for image-to-video.
                "personGeneration": "allow_adult",
            },
        }

        operation_payload = None
        for model in deduped_models:
            endpoint = f"{base_url}/models/{model}:predictLongRunning"
            try:
                create_response = requests.post(
                    endpoint,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=(20, 120),
                )
                create_response.raise_for_status()
                operation_payload = create_response.json()
                break
            except requests.HTTPError as exc:
                response_preview = ""
                if exc.response is not None:
                    response_preview = exc.response.text[:500]
                if get_verbose():
                    warning(
                        f"Gemini Veo request failed for model {model}: {exc}. "
                        f"Response: {response_preview}"
                    )
            except Exception as exc:
                if get_verbose():
                    warning(f"Gemini Veo request failed for model {model}: {exc}")

        if operation_payload is None:
            return None

        operation_name = str(operation_payload.get("name") or "").strip()
        if not operation_name:
            if get_verbose():
                warning(f"Gemini Veo 3.1 returned no operation name: {operation_payload}")
            return None

        poll_deadline = time.time() + get_gemini_veo_timeout_seconds()
        poll_interval = get_gemini_veo_poll_interval_seconds()
        poll_url = f"{base_url}/{operation_name.lstrip('/')}"
        last_payload = operation_payload

        while time.time() < poll_deadline:
            try:
                status_response = requests.get(
                    poll_url,
                    headers={"x-goog-api-key": api_key},
                    timeout=(20, 90),
                )
                status_response.raise_for_status()
                last_payload = status_response.json()
            except Exception as exc:
                if get_verbose():
                    warning(f"Gemini Veo poll failed: {exc}")
                time.sleep(poll_interval)
                continue

            if last_payload.get("done") is True:
                if last_payload.get("error"):
                    if get_verbose():
                        warning(f"Gemini Veo operation failed: {last_payload.get('error')}")
                    return None
                break

            time.sleep(poll_interval)
        else:
            if get_verbose():
                warning("Gemini Veo operation timed out before completion.")
            return None

        video_uri = self._extract_gemini_video_uri(last_payload)
        if not video_uri:
            if get_verbose():
                warning(f"Gemini Veo returned no downloadable video URI: {last_payload}")
            return None

        return self._download_video_with_growth_guard(
            video_uri,
            "Gemini Veo 3.1",
            headers={"x-goog-api-key": api_key},
        )

    def generate_motion_clip(self, prompt: str, image_path: str) -> str | None:
        """
        Routes motion generation to the configured provider.

        Args:
            prompt (str): Motion prompt
            image_path (str): Input image path

        Returns:
            path (str | None): Motion clip path
        """
        provider = str(get_video_motion_provider() or "gemini_veo31").strip().lower()
        if provider in {"none", "off", "disabled"}:
            return None
        if provider in {"gemini", "gemini_veo31", "veo31"}:
            return self.generate_motion_clip_gemini_veo31(prompt, image_path)
        if provider in {"fal", "fal_veo3", "veo3"}:
            return self.generate_motion_clip_veo3(prompt, image_path)
        return None

    def generate_image(self, prompt: str) -> str:
        """
        Generates an AI Image based on the given prompt using Nano Banana 2.

        Args:
            prompt (str): Reference for image generation

        Returns:
            path (str): The path to the generated image.
        """
        enhanced_prompt = self._enhance_visual_prompt(prompt)
        generated = None

        image_provider = str(get_video_image_provider() or "gemini").strip().lower()

        # Optional HQ path with fal Nano Banana Pro.
        if self._is_hq_mode() and image_provider == "fal":
            generated = self.generate_image_fal_nanobanana_pro(enhanced_prompt)

        if not generated:
            generated = self.generate_image_nanobanana2(enhanced_prompt)

        if generated:
            return generated

        warning("Nano Banana 2 did not return an image. Falling back to local placeholder image.")
        return self._create_fallback_image(prompt)

    def _create_fallback_image(self, prompt: str) -> str:
        """
        Creates a local placeholder image when the remote image provider fails.

        Args:
            prompt (str): Prompt text for context

        Returns:
            path (str): The path to the generated fallback image
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")
        canvas = Image.new("RGB", (1080, 1920), color=(23, 32, 42))
        draw = ImageDraw.Draw(canvas)

        title = "Creator Growth Placeholder Visual"
        subject = f"Subject: {self.subject}" if hasattr(self, "subject") else "Subject: automation"
        prompt_text = f"Prompt: {prompt}"
        wrapped_prompt = "\n".join(textwrap.wrap(prompt_text, width=44))[:1100]
        text_block = f"{title}\n\n{subject}\n\n{wrapped_prompt}"

        draw.rectangle([(48, 96), (1032, 1824)], outline=(96, 146, 187), width=6)
        draw.multiline_text((86, 140), text_block, fill=(235, 242, 248), spacing=14)
        canvas.save(image_path, "PNG")

        self.images.append(image_path)
        if get_verbose():
            info(f' => Wrote fallback image to "{image_path}"')

        return image_path

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using KittenTTS and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r"[^\w\s.?!]", "", self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path

        if get_verbose():
            info(f' => Wrote TTS to "{path}"')

        return path

    def add_video(self, video: dict) -> None:
        """
        Adds a video to the cache.

        Args:
            video (dict): The video to add

        Returns:
            None
        """
        videos = self.get_videos()
        videos.append(video)

        cache = get_youtube_cache_path()

        with open(cache, "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self._account_uuid:
                    account["videos"].append(video)

            # Commit changes
            with open(cache, "w") as f:
                f.write(json.dumps(previous_json))

    def generate_subtitles(self, audio_path: str) -> str:
        """
        Generates subtitles for the audio using the configured STT provider.

        Args:
            audio_path (str): The path to the audio file.

        Returns:
            path (str): The path to the generated SRT File.
        """
        subtitle_source = str(get_youtube_subtitle_source() or "script").strip().lower()
        if subtitle_source == "script":
            try:
                return self.generate_subtitles_from_script(audio_path)
            except Exception as exc:
                warning(f"Script-based subtitles failed, falling back to STT: {exc}")

        provider = str(get_stt_provider() or "local_whisper").lower()

        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)

        if provider == "third_party_assemblyai":
            return self.generate_subtitles_assemblyai(audio_path)

        warning(f"Unknown stt_provider '{provider}'. Falling back to local_whisper.")
        return self.generate_subtitles_local_whisper(audio_path)

    def generate_subtitles_from_script(self, audio_path: str) -> str:
        """
        Generates subtitles directly from the finalized script and aligns them
        across the final voiceover duration.

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        script_text = self._clean_text_response(getattr(self, "script", ""))
        if not script_text:
            raise RuntimeError("Script text is empty; cannot generate script-based subtitles.")

        audio_clip = AudioFileClip(audio_path)
        try:
            total_duration = max(1.0, float(audio_clip.duration))
        finally:
            audio_clip.close()

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", script_text)
            if sentence and sentence.strip()
        ]

        if not sentences:
            raise RuntimeError("Could not split script into subtitle sentences.")

        # Fallback chunking for scripts without punctuation.
        if len(sentences) == 1 and len(sentences[0].split()) > 12:
            words = sentences[0].split()
            sentences = []
            chunk_size = 8
            for idx in range(0, len(words), chunk_size):
                sentences.append(" ".join(words[idx: idx + chunk_size]).strip())

        word_counts = [max(1, len(segment.split())) for segment in sentences]
        total_words = max(1, sum(word_counts))

        cursor = 0.0
        lines: list[str] = []
        for idx, segment in enumerate(sentences, start=1):
            share = word_counts[idx - 1] / total_words
            duration = max(0.7, total_duration * share)
            start = cursor
            end = min(total_duration, start + duration)
            cursor = end

            lines.append(str(idx))
            lines.append(
                f"{self._format_srt_timestamp(start)} --> {self._format_srt_timestamp(end)}"
            )
            lines.append(segment)
            lines.append("")

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write("\n".join(lines))

        return srt_path

    def generate_subtitles_assemblyai(self, audio_path: str) -> str:
        """
        Generates subtitles using AssemblyAI.

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        aai.settings.api_key = get_assemblyai_api_key()
        config = aai.TranscriptionConfig()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)
        subtitles = transcript.export_subtitles_srt()

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")

        with open(srt_path, "w") as file:
            file.write(subtitles)

        return srt_path

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Formats a timestamp in seconds to SRT format.

        Args:
            seconds (float): Seconds

        Returns:
            ts (str): HH:MM:SS,mmm
        """
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3600000
        minutes = (total_millis % 3600000) // 60000
        secs = (total_millis % 60000) // 1000
        millis = total_millis % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_subtitles_local_whisper(self, audio_path: str) -> str:
        """
        Generates subtitles using local Whisper (faster-whisper).

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            error(
                "Local STT selected but 'faster-whisper' is not installed. "
                "Install it or switch stt_provider to third_party_assemblyai."
            )
            raise

        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        script_language = (get_youtube_script_language() or self.language or "").strip().lower()
        if script_language in {"filipino", "tagalog", "fil", "tl"}:
            segments, _ = model.transcribe(audio_path, vad_filter=True, language="tl")
        else:
            segments, _ = model.transcribe(audio_path, vad_filter=True)

        lines = []
        for idx, segment in enumerate(segments, start=1):
            start = self._format_srt_timestamp(segment.start)
            end = self._format_srt_timestamp(segment.end)
            text = str(segment.text).strip()

            if not text:
                continue

            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        subtitles = "\n".join(lines)
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        tts_clip = AudioFileClip(self.tts_path)
        max_allowed_duration = float(get_youtube_max_short_duration_seconds())
        max_duration = min(float(tts_clip.duration), max_allowed_duration)
        if float(tts_clip.duration) > max_allowed_duration:
            warning(
                f"Voiceover exceeded short limit; clipping from {tts_clip.duration:.2f}s to {max_duration:.2f}s."
            )
            tts_clip = tts_clip.subclip(0, max_duration)
        if len(self.images) == 0:
            raise RuntimeError("No images were generated for video composition.")
        req_dur = max_duration / len(self.images)

        # Make a generator that returns a TextClip when called with consecutive
        generator = lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=58,
            color="#FFFFFF",
            stroke_color="black",
            stroke_width=3,
            size=(920, None),
            method="caption",
            align="center",
        )

        print(colored("[+] Combining images...", "blue"))

        clip_sequence = []
        self.motion_clips = [None for _ in self.images]

        # Optional HQ enhancement: animate a few stills with Veo image-to-video.
        if self._is_hq_mode() and get_fal_enable_veo_motion():
            motion_limit = min(len(self.images), get_fal_motion_clip_limit())
            if motion_limit > 0:
                for idx in range(motion_limit):
                    prompt_hint = (
                        self.image_prompts[idx]
                        if hasattr(self, "image_prompts") and idx < len(self.image_prompts)
                        else self.subject
                    )
                    motion_clip = self.generate_motion_clip(prompt_hint, self.images[idx])
                    if motion_clip:
                        self.motion_clips[idx] = motion_clip

        for idx, image_path in enumerate(self.images):
            clip = None
            motion_path = self.motion_clips[idx] if idx < len(self.motion_clips) else None

            if motion_path and os.path.exists(motion_path):
                try:
                    clip = VideoFileClip(motion_path).without_audio().set_fps(30)
                    if clip.duration < req_dur:
                        clip = clip.fx(vfx.loop, duration=req_dur)
                    clip = clip.subclip(0, req_dur)
                except Exception as exc:
                    warning(f"Could not load Veo motion clip, using still image instead: {exc}")
                    clip = None

            if clip is None:
                clip = ImageClip(image_path).set_duration(req_dur).set_fps(30)

            # Not all media are the same size, so normalize to 9:16.
            if round((clip.w / clip.h), 4) < 0.5625:
                if get_verbose():
                    info(f" => Resizing media: {image_path} to 1080x1920")
                clip = crop(
                    clip,
                    width=clip.w,
                    height=round(clip.w / 0.5625),
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                )
            else:
                if get_verbose():
                    info(f" => Resizing media: {image_path} to 1080x1920")
                clip = crop(
                    clip,
                    width=round(0.5625 * clip.h),
                    height=clip.h,
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                )
            clip = clip.resize((1080, 1920))
            clip_sequence.append(clip)

        final_clip = concatenate_videoclips(clip_sequence, method="compose")
        final_clip = final_clip.set_fps(30)
        random_song = choose_random_song()

        subtitles = None
        try:
            subtitles_path = self.generate_subtitles(self.tts_path)
            equalize_subtitles(subtitles_path, 18)
            subtitles = SubtitlesClip(subtitles_path, generator)
            subtitles = subtitles.set_pos(("center", get_video_subtitle_y()))
        except Exception as e:
            warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        random_song_clip = AudioFileClip(random_song).set_fps(44100)

        # Turn down volume
        random_song_clip = random_song_clip.fx(afx.volumex, 0.1)
        comp_audio = CompositeAudioClip([tts_clip.set_fps(44100), random_song_clip])

        final_clip = final_clip.set_audio(comp_audio)
        final_clip = final_clip.set_duration(max_duration)

        overlays = [final_clip]

        hook_text = str(self.subject or self.metadata.get("title") or "").strip()
        if hook_text:
            hook_words = hook_text.split()
            hook_text = " ".join(hook_words[:3]).upper()
            try:
                hook_clip = TextClip(
                    hook_text,
                    font=os.path.join(get_fonts_dir(), get_font()),
                    fontsize=112,
                    color="#FFFFFF",
                    stroke_color="black",
                    stroke_width=6,
                    size=(1020, None),
                    method="caption",
                    align="center",
                ).set_position(("center", get_video_hook_y())).set_duration(max_duration)
                overlays.append(hook_clip)
            except Exception:
                pass

        if subtitles is not None:
            overlays.append(subtitles)

        if len(overlays) > 1:
            final_clip = CompositeVideoClip(overlays)

        # Suppress ffmpeg progress spam to keep worker event streams readable.
        final_clip.write_videofile(
            combined_image_path,
            threads=threads,
            codec="libx264",
            audio_codec="aac",
            bitrate="10M",
            logger=None,
            verbose=False,
        )

        success(f'Wrote Video to "{combined_image_path}"')

        return combined_image_path

    def generate_video(self, tts_instance: TTS, longform_content: str = None) -> str:
        """
        Generates a YouTube Short based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.
            longform_content (str): Optional long-form content to summarize into a Short.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        # Generate the Topic
        self.generate_topic()

        # Generate the Script
        self.generate_script(longform_content)

        # Generate the Metadata
        self.generate_metadata()

        # Generate the Image Prompts
        self.generate_prompts()

        # Generate the Images
        for prompt in self.image_prompts:
            self.generate_image(prompt)

        # Generate the TTS
        self.generate_script_to_speech(tts_instance)

        # Combine everything
        path = self.combine()

        if get_verbose():
            info(f" => Generated Video: {path}")

        self.video_path = os.path.abspath(path)

        return path

    def get_channel_id(self) -> str:
        """
        Gets the Channel ID of the YouTube Account.

        Returns:
            channel_id (str): The Channel ID.
        """
        driver = self.browser
        driver.get("https://studio.youtube.com")
        try:
            wait = WebDriverWait(driver, 30)
            wait.until(lambda current_driver: "studio.youtube.com" in current_driver.current_url)
            wait.until(
                lambda current_driver: current_driver.execute_script("return document.readyState")
                == "complete"
            )
        except Exception:
            pass

        channel_id = ""
        current_url = driver.current_url
        channel_match = re.search(r"/channel/([^/?]+)", current_url)
        if channel_match:
            channel_id = channel_match.group(1)

        if not channel_id:
            for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href*='/channel/']"):
                href = anchor.get_attribute("href") or ""
                channel_match = re.search(r"/channel/([^/?]+)", href)
                if channel_match:
                    channel_id = channel_match.group(1)
                    break

        self.channel_id = channel_id

        return channel_id

    def _wait_for_any(
        self,
        selectors: List[tuple[str, str]],
        clickable: bool = False,
        timeout: int = 40,
    ) -> Any:
        """
        Waits for the first available selector from a selector list.

        Args:
            selectors (List[tuple[str, str]]): Ordered list of selectors
            clickable (bool): Whether the target must be clickable
            timeout (int): Wait timeout in seconds for each selector

        Returns:
            element (Any): Selenium WebElement
        """
        wait = WebDriverWait(self.browser, timeout)
        last_error: Exception | None = None

        for by, value in selectors:
            try:
                if clickable:
                    return wait.until(EC.element_to_be_clickable((by, value)))
                return wait.until(EC.presence_of_element_located((by, value)))
            except Exception as exc:
                last_error = exc

        selector_preview = ", ".join([f"{item[0]}={item[1]}" for item in selectors])
        raise RuntimeError(f"Could not locate required YouTube element. Tried: {selector_preview}") from last_error

    def _set_textbox_value(
        self,
        element: Any,
        value: str,
        selectors: List[tuple[str, str]] | None = None,
    ) -> None:
        """
        Sets the value of a contenteditable textbox in YouTube Studio.

        Args:
            element (Any): Selenium WebElement
            value (str): Value to set

        Returns:
            None
        """
        text_value = str(value or "")
        normalized = text_value.strip()
        last_error: Exception | None = None

        for _ in range(3):
            try:
                self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

                # YouTube hashtag suggestions can overlay the editable area and intercept clicks.
                try:
                    element.click()
                except Exception:
                    self.browser.execute_script("arguments[0].focus();", element)

                try:
                    element.send_keys(Keys.ESCAPE)
                except Exception:
                    pass

                element.send_keys(Keys.CONTROL, "a")
                element.send_keys(Keys.BACKSPACE)
                if text_value:
                    element.send_keys(text_value)

                current_value = (
                    element.get_attribute("innerText")
                    or element.get_attribute("textContent")
                    or element.text
                    or ""
                ).strip()
                if current_value == normalized:
                    return

                raise RuntimeError("Textbox value mismatch after keyboard input.")
            except Exception as exc:
                last_error = exc
                try:
                    self.browser.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                except Exception:
                    pass

                # Fallback to JS assignment to avoid click-interception overlays.
                try:
                    self.browser.execute_script(
                        """
                        const target = arguments[0];
                        const nextValue = arguments[1];
                        target.focus();
                        target.textContent = nextValue;
                        target.dispatchEvent(new Event('input', { bubbles: true }));
                        target.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        element,
                        text_value,
                    )
                    current_value = (
                        element.get_attribute("innerText")
                        or element.get_attribute("textContent")
                        or element.text
                        or ""
                    ).strip()
                    if current_value == normalized:
                        return
                except Exception as js_exc:
                    last_error = js_exc

                if selectors:
                    try:
                        element = self._wait_for_any(selectors, clickable=False, timeout=20)
                    except Exception:
                        pass

                time.sleep(0.4)

        raise RuntimeError(f"Could not set textbox value: {last_error}") from last_error

    def _normalize_text_for_compare(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    def _read_textbox_value(self, selectors: List[tuple[str, str]]) -> str:
        element = self._wait_for_any(selectors, clickable=False, timeout=30)
        try:
            raw = self.browser.execute_script(
                "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                element,
            )
            return str(raw or "").strip()
        except Exception:
            return (
                element.get_attribute("innerText")
                or element.get_attribute("textContent")
                or element.text
                or ""
            ).strip()

    def _set_upload_metadata(
        self,
        title: str,
        description: str,
        title_selectors: List[tuple[str, str]],
        description_selectors: List[tuple[str, str]],
    ) -> None:
        target_title = self._normalize_text_for_compare(title)
        target_description = self._normalize_text_for_compare(description)
        last_seen_title = ""
        last_seen_description = ""

        for attempt in range(1, 4):
            title_el = self._wait_for_any(title_selectors, clickable=True, timeout=90)
            self._set_textbox_value(title_el, title, selectors=title_selectors)

            description_el = self._wait_for_any(description_selectors, clickable=True, timeout=90)
            self._set_textbox_value(description_el, description, selectors=description_selectors)

            # Let Studio apply any deferred value sync before verification.
            time.sleep(1.0)

            last_seen_title = self._normalize_text_for_compare(self._read_textbox_value(title_selectors))
            last_seen_description = self._normalize_text_for_compare(self._read_textbox_value(description_selectors))

            if last_seen_title == target_title and last_seen_description == target_description:
                try:
                    self.browser.find_element(By.TAG_NAME, "body").send_keys(Keys.TAB)
                    time.sleep(0.3)
                except Exception:
                    pass
                return

            warning(
                "YouTube metadata fields changed after entry; retrying "
                f"({attempt}/3)."
            )

        raise RuntimeError(
            "Could not persist YouTube title/description before publish. "
            f"Last seen title='{last_seen_title}' description='{last_seen_description}'."
        )

    def _extract_uploaded_video_url(self, expected_title: str | None = None) -> str | None:
        """
        Attempts to read the latest uploaded video URL.

        Returns:
            url (str | None): Public watch URL when available
        """
        for anchor in self.browser.find_elements(By.CSS_SELECTOR, "a[href*='watch?v=']"):
            href = (anchor.get_attribute("href") or "").strip()
            match = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", href)
            if not match:
                continue
            video_id = match.group(1)
            if video_id.lower() == "edit":
                continue
            return build_url(video_id)

        if not self.channel_id:
            return None

        self.browser.get(f"https://studio.youtube.com/channel/{self.channel_id}/videos/short")
        time.sleep(3)

        expected_normalized = self._normalize_text_for_compare(expected_title or "").lower()
        expected_prefix = expected_normalized[:36] if expected_normalized else ""

        rows = self.browser.find_elements(By.TAG_NAME, "ytcp-video-row")
        for row in rows[:8]:
            try:
                if expected_prefix:
                    row_text = self._normalize_text_for_compare(row.text).lower()
                    if expected_prefix not in row_text:
                        continue

                anchor = row.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                href = (anchor.get_attribute("href") or "").strip()
                if "/video/" not in href:
                    continue

                video_id = href.rstrip("/").split("/")[-1]
                if video_id and video_id.lower() != "edit":
                    return build_url(video_id)
            except Exception:
                continue

        return None

    def _wait_for_upload_confirmation(
        self,
        expected_title: str,
        timeout_seconds: int,
    ) -> tuple[bool, str | None]:
        """
        Waits until YouTube Studio shows the uploaded video entry.

        Args:
            expected_title (str): Expected video title
            timeout_seconds (int): Wait timeout

        Returns:
            confirmed (tuple[bool, str | None]): Whether upload is confirmed and optional watch URL
        """
        deadline = time.time() + max(60, int(timeout_seconds))
        expected_normalized = self._normalize_text_for_compare(expected_title).lower()
        expected_prefix = expected_normalized[:36] if expected_normalized else ""
        last_seen_hint = ""

        while time.time() < deadline:
            # Fast-path: if current page exposes a watch URL, use it.
            url = self._extract_uploaded_video_url(expected_title=expected_title)
            if url:
                return True, url

            if self.channel_id:
                self.browser.get(f"https://studio.youtube.com/channel/{self.channel_id}/videos/short")
                time.sleep(3)

                rows = self.browser.find_elements(By.TAG_NAME, "ytcp-video-row")
                for row in rows[:10]:
                    row_text = self._normalize_text_for_compare(row.text)
                    row_text_lower = row_text.lower()
                    if row_text:
                        last_seen_hint = row_text[:200]

                    if expected_prefix and expected_prefix not in row_text_lower:
                        continue

                    try:
                        anchor = row.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                        href = (anchor.get_attribute("href") or "").strip()
                        video_id = ""
                        if "/video/" in href:
                            video_id = href.rstrip("/").split("/")[-1]
                        if video_id and video_id.lower() != "edit":
                            return True, build_url(video_id)
                    except Exception:
                        # Entry exists but URL selector unavailable yet.
                        return True, None

            time.sleep(8)

        if last_seen_hint:
            warning(f"Upload confirmation timeout. Last Studio row sample: {last_seen_hint}")
        return False, None

    def upload_video(self) -> bool:
        """
        Uploads the video to YouTube.

        Returns:
            success (bool): Whether the upload was successful or not.
        """
        driver = self.browser
        verbose = get_verbose()
        self.last_upload_error = None
        upload_submitted = False

        try:
            self.get_channel_id()

            file_input_selectors = [
                (By.CSS_SELECTOR, "input[type='file'][name='Filedata']"),
                (By.CSS_SELECTOR, "ytcp-uploads-file-picker input[type='file']"),
                (By.CSS_SELECTOR, "input[type='file']"),
            ]

            # This route consistently opens the upload dialog and exposes the
            # file picker when already authenticated.
            driver.get("https://www.youtube.com/upload")

            try:
                file_input = self._wait_for_any(file_input_selectors, timeout=45)
            except Exception:
                # Fallback: channel-scoped upload route with d=ud query param.
                if self.channel_id:
                    driver.get(
                        f"https://studio.youtube.com/channel/{self.channel_id}/videos/upload?d=ud"
                    )
                else:
                    driver.get("https://studio.youtube.com/videos/upload?d=ud")

                try:
                    file_input = self._wait_for_any(file_input_selectors, timeout=45)
                except Exception:
                    # Last fallback: click Create -> Upload videos from Studio.
                    create_button = self._wait_for_any(
                        [
                            (By.CSS_SELECTOR, "ytcp-button#create-icon"),
                            (By.CSS_SELECTOR, "#create-icon"),
                            (By.XPATH, "//button[@aria-label='Create']"),
                        ],
                        clickable=True,
                        timeout=30,
                    )
                    driver.execute_script("arguments[0].click();", create_button)

                    upload_menu_item = self._wait_for_any(
                        [
                            (By.XPATH, "//tp-yt-paper-item//*[contains(., 'Upload videos')]"),
                            (By.XPATH, "//*[contains(@test-id, 'upload')]"),
                        ],
                        clickable=True,
                        timeout=30,
                    )
                    driver.execute_script("arguments[0].click();", upload_menu_item)
                    file_input = self._wait_for_any(file_input_selectors, timeout=45)

            file_input.send_keys(self.video_path)

            if verbose:
                info("\t=> Video file selected.")

            title_selectors = [
                (By.CSS_SELECTOR, "ytcp-social-suggestions-textbox#title-textarea #textbox"),
                (By.CSS_SELECTOR, "#title-textarea #textbox"),
                (By.XPATH, "(//*[@id='textbox'])[1]"),
            ]

            description_selectors = [
                (By.CSS_SELECTOR, "ytcp-social-suggestions-textbox#description-textarea #textbox"),
                (By.CSS_SELECTOR, "#description-textarea #textbox"),
                (By.XPATH, "(//*[@id='textbox'])[2]"),
            ]

            if verbose:
                info("\t=> Setting title and description...")

            self._set_upload_metadata(
                str(self.metadata["title"])[:100],
                str(self.metadata["description"]),
                title_selectors,
                description_selectors,
            )

            # Set `made for kids` option
            if verbose:
                info("\t=> Setting `made for kids` option...")

            if get_is_for_kids():
                kids_option = self._wait_for_any(
                    [
                        (By.NAME, YOUTUBE_MADE_FOR_KIDS_NAME),
                        (By.XPATH, "//tp-yt-paper-radio-button[@name='VIDEO_MADE_FOR_KIDS_MFK']"),
                    ],
                    clickable=True,
                )
            else:
                kids_option = self._wait_for_any(
                    [
                        (By.NAME, YOUTUBE_NOT_MADE_FOR_KIDS_NAME),
                        (By.XPATH, "//tp-yt-paper-radio-button[@name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"),
                    ],
                    clickable=True,
                )
            driver.execute_script("arguments[0].click();", kids_option)

            for step_number in range(3):
                if verbose:
                    info(f"\t=> Clicking next ({step_number + 1}/3)...")
                next_button = self._wait_for_any(
                    [
                        (By.ID, YOUTUBE_NEXT_BUTTON_ID),
                        (By.CSS_SELECTOR, "#next-button button"),
                        (By.XPATH, "//ytcp-button[@id='next-button']//button"),
                    ],
                    clickable=True,
                    timeout=60,
                )
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(1)

            # Set as unlisted
            if verbose:
                info("\t=> Setting as unlisted...")

            unlisted_radio = self._wait_for_any(
                [
                    (By.XPATH, "//tp-yt-paper-radio-button[@name='UNLISTED']"),
                    (By.XPATH, "//*[@name='UNLISTED']"),
                    (By.XPATH, "//yt-formatted-string[contains(., 'Unlisted')]/ancestor::tp-yt-paper-radio-button[1]"),
                ],
                clickable=True,
                timeout=60,
            )
            driver.execute_script("arguments[0].click();", unlisted_radio)

            if verbose:
                info("\t=> Clicking done button...")

            done_button = self._wait_for_any(
                [
                    (By.ID, YOUTUBE_DONE_BUTTON_ID),
                    (By.CSS_SELECTOR, "#done-button button"),
                    (By.XPATH, "//ytcp-button[@id='done-button']//button"),
                ],
                clickable=True,
                timeout=180,
            )
            driver.execute_script("arguments[0].click();", done_button)
            upload_submitted = True
            time.sleep(3)

            confirmed, url = self._wait_for_upload_confirmation(
                expected_title=str(self.metadata.get("title") or ""),
                timeout_seconds=get_youtube_upload_confirm_timeout_seconds(),
            )
            if not confirmed:
                raise RuntimeError(
                    "YouTube upload was submitted but could not be confirmed in Studio before timeout."
                )

            self.uploaded_video_url = url or ""

            if url:
                if verbose:
                    success(f" => Uploaded Video: {url}")
            elif verbose:
                warning(
                    "Upload entry confirmed in Studio, but a public watch URL "
                    "could not be resolved yet."
                )

            # Add video to cache
            self.add_video(
                {
                    "title": self.metadata["title"],
                    "description": self.metadata["description"],
                    "url": self.uploaded_video_url,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            return True
        except Exception as exc:
            self.last_upload_error = f"{type(exc).__name__}: {exc}"
            error(f"YouTube upload failed: {self.last_upload_error}")
            if verbose:
                traceback.print_exc()
            return False
        finally:
            if not upload_submitted and verbose:
                warning("YouTube upload did not reach final submission.")
            self.quit()

    def get_videos(self) -> List[dict]:
        """
        Gets the uploaded videos from the YouTube Channel.

        Returns:
            videos (List[dict]): The uploaded videos.
        """
        if not os.path.exists(get_youtube_cache_path()):
            # Create the cache file
            with open(get_youtube_cache_path(), "w") as file:
                json.dump({"videos": []}, file, indent=4)
            return []

        videos = []
        # Read the cache file
        with open(get_youtube_cache_path(), "r") as file:
            previous_json = json.loads(file.read())
            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self._account_uuid:
                    videos = account["videos"]

        return videos

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
