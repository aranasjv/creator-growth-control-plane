import re
import base64
import json
import time
import os
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

        self.images = []

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

    def generate_topic(self) -> str:
        """
        Generates a topic based on the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        from llm_provider import get_managed_prompt
        prompt_text = get_managed_prompt(
            "youtube_topic_generation",
            default_prompt="Please generate a specific video idea that takes about the following topic: {niche}. Make it exactly one sentence. Only return the topic, nothing else.",
            niche=self.niche
        )
        completion = self.generate_response(prompt_text)

        if not completion:
            error("Failed to generate Topic.")

        self.subject = completion

        return completion

    def generate_script(self, longform_content: str = None) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        from llm_provider import get_managed_prompt
        
        if longform_content:
            prompt_text = get_managed_prompt(
                "short_from_longform_script",
                default_prompt="Summarize the following long form content into a highly engaging {sentence_length}-sentence script. Make it punchy, hook the viewer in the first sentence, and deliver value. DO NOT INCLUDE ANY FORMATTING LIKE 'VOICEOVER:' OR MENTION THE PROMPT. ONLY RETURN THE SCRIPT TEXT.\n\nContent:\n{content}",
                sentence_length=sentence_length,
                content=longform_content
            )
        else:
            prompt_text = get_managed_prompt(
                "youtube_script_generation",
                default_prompt=f"Generate a script for a video in {sentence_length} sentences, depending on the subject {self.subject} in {self.language}.",
                sentence_length=sentence_length,
                subject=self.subject,
                language=self.language
            )

        completion = self.generate_response(prompt_text)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            return

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()

        self.script = completion

        return completion

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description).

        Returns:
            metadata (dict): The generated metadata.
        """
        from llm_provider import get_managed_prompt
        title_prompt = get_managed_prompt(
            "youtube_metadata_title",
            default_prompt="Please generate a YouTube Video Title for the following subject, including hashtags: {subject}. Only return the title, nothing else. Limit the title under 100 characters.",
            subject=self.subject
        )
        title = self.generate_response(title_prompt)

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        desc_prompt = get_managed_prompt(
            "youtube_metadata_description",
            default_prompt="Please generate a YouTube Video Description for the following script: {script}. Only return the description, nothing else.",
            script=self.script
        )
        description = self.generate_response(desc_prompt)

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
        estimated_from_sentences = max(6, len(sentence_candidates) * 2)
        n_prompts = min(24, estimated_from_sentences)

        from llm_provider import get_managed_prompt
        prompt_text = get_managed_prompt(
            "youtube_image_prompts",
            default_prompt=f"Generate {n_prompts} Image Prompts for AI Image Generation for subject: {self.subject}. Return as JSON-Array of strings. Script context:\n{self.script}",
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
            "Vertical 9:16, cinematic close-up composition, expressive 3D animated subject, "
            "high detail, dramatic soft lighting, shallow depth of field, tactile textures, "
            "high contrast, emotional framing, no text overlay, no watermark."
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

        try:
            response = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
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
            if get_verbose():
                warning(f"Failed to generate image with Nano Banana 2 API: {str(e)}")
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
        provider = str(get_stt_provider() or "local_whisper").lower()

        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)

        if provider == "third_party_assemblyai":
            return self.generate_subtitles_assemblyai(audio_path)

        warning(f"Unknown stt_provider '{provider}'. Falling back to local_whisper.")
        return self.generate_subtitles_local_whisper(audio_path)

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
        max_duration = tts_clip.duration
        if len(self.images) == 0:
            raise RuntimeError("No images were generated for video composition.")
        req_dur = max_duration / len(self.images)

        # Make a generator that returns a TextClip when called with consecutive
        generator = lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=72,
            color="#FFFFFF",
            stroke_color="black",
            stroke_width=3,
            size=(980, None),
            method="caption",
            align="center",
        )

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        while tot_dur < max_duration:
            for image_path in self.images:
                clip = ImageClip(image_path)
                clip.duration = req_dur
                clip = clip.set_fps(30)

                # Not all images are same size,
                # so we need to resize them
                if round((clip.w / clip.h), 4) < 0.5625:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1080x1920")
                    clip = crop(
                        clip,
                        width=clip.w,
                        height=round(clip.w / 0.5625),
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                else:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1920x1080")
                    clip = crop(
                        clip,
                        width=round(0.5625 * clip.h),
                        height=clip.h,
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                clip = clip.resize((1080, 1920))

                # FX (Fade In)
                # clip = clip.fadein(2)

                clips.append(clip)
                tot_dur += clip.duration

        final_clip = concatenate_videoclips(clips)
        final_clip = final_clip.set_fps(30)
        random_song = choose_random_song()

        subtitles = None
        try:
            subtitles_path = self.generate_subtitles(self.tts_path)
            equalize_subtitles(subtitles_path, 18)
            subtitles = SubtitlesClip(subtitles_path, generator)
            subtitles = subtitles.set_pos(("center", 240))
        except Exception as e:
            warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        random_song_clip = AudioFileClip(random_song).set_fps(44100)

        # Turn down volume
        random_song_clip = random_song_clip.fx(afx.volumex, 0.1)
        comp_audio = CompositeAudioClip([tts_clip.set_fps(44100), random_song_clip])

        final_clip = final_clip.set_audio(comp_audio)
        final_clip = final_clip.set_duration(tts_clip.duration)

        overlays = [final_clip]

        hook_text = str(self.metadata.get("title") or "").strip()
        if hook_text:
            hook_words = hook_text.split()
            hook_text = " ".join(hook_words[:3]).upper()
            try:
                hook_clip = TextClip(
                    hook_text,
                    font=os.path.join(get_fonts_dir(), get_font()),
                    fontsize=120,
                    color="#FFFFFF",
                    stroke_color="black",
                    stroke_width=6,
                    size=(980, None),
                    method="caption",
                    align="center",
                ).set_position(("center", 70)).set_duration(tts_clip.duration)
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

    def _extract_uploaded_video_url(self) -> str | None:
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

        rows = self.browser.find_elements(By.TAG_NAME, "ytcp-video-row")
        for row in rows[:3]:
            try:
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

            url = self._extract_uploaded_video_url()
            self.uploaded_video_url = url or ""

            if url and verbose:
                success(f" => Uploaded Video: {url}")
            elif verbose:
                warning("Upload submitted but a public video URL could not be resolved yet.")

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
