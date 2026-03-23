import os
import sys
import json
import srt_equalizer

from termcolor import colored

ROOT_DIR = os.path.dirname(sys.path[0])

def get_job_parameters() -> dict:
    """
    Gets per-job parameters passed through the worker environment.

    Returns:
        params (dict): The parsed job parameters
    """
    raw = os.environ.get("CGCP_JOB_PARAMETERS", "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}

def assert_folder_structure() -> None:
    """
    Make sure that the nessecary folder structure is present.

    Returns:
        None
    """
    # Create the .mp folder
    if not os.path.exists(os.path.join(ROOT_DIR, ".mp")):
        if get_verbose():
            print(colored(f"=> Creating .mp folder at {os.path.join(ROOT_DIR, '.mp')}", "green"))
        os.makedirs(os.path.join(ROOT_DIR, ".mp"))

def get_first_time_running() -> bool:
    """
    Checks if the program is running for the first time by checking if .mp folder exists.

    Returns:
        exists (bool): True if the program is running for the first time, False otherwise
    """
    return not os.path.exists(os.path.join(ROOT_DIR, ".mp"))

def get_email_credentials() -> dict:
    """
    Gets the email credentials from the config file.

    Returns:
        credentials (dict): The email credentials
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["email"]

def get_verbose() -> bool:
    """
    Gets the verbose flag from the config file.

    Returns:
        verbose (bool): The verbose flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["verbose"]

def get_firefox_profile_path() -> str:
    """
    Gets the path to the Firefox profile.

    Returns:
        path (str): The path to the Firefox profile
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["firefox_profile"]

def get_headless() -> bool:
    """
    Gets the headless flag from the config file.

    Returns:
        headless (bool): The headless flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["headless"]

def get_ollama_base_url() -> str:
    """
    Gets the Ollama base URL.

    Returns:
        url (str): The Ollama base URL
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("ollama_base_url", "http://127.0.0.1:11434")

def get_ollama_model() -> str:
    """
    Gets the Ollama model name from the config file.

    Returns:
        model (str): The Ollama model name, or empty string if not set.
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("ollama_model", "")

def get_twitter_language() -> str:
    """
    Gets the Twitter language from the config file.

    Returns:
        language (str): The Twitter language
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["twitter_language"]

def get_nanobanana2_api_base_url() -> str:
    """
    Gets the Nano Banana 2 (Gemini image) API base URL.

    Returns:
        url (str): API base URL
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get(
            "nanobanana2_api_base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        )

def get_nanobanana2_api_key() -> str:
    """
    Gets the Nano Banana 2 API key.

    Returns:
        key (str): API key
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = json.load(file).get("nanobanana2_api_key", "")
        return configured or os.environ.get("GEMINI_API_KEY", "")

def get_nanobanana2_model() -> str:
    """
    Gets the Nano Banana 2 model name.

    Returns:
        model (str): Model name
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("nanobanana2_model", "gemini-3.1-flash-image-preview")

def get_nanobanana2_aspect_ratio() -> str:
    """
    Gets the aspect ratio for Nano Banana 2 image generation.

    Returns:
        ratio (str): Aspect ratio
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("nanobanana2_aspect_ratio", "9:16")

def get_nanobanana2_timeout_seconds() -> int:
    """
    Gets read timeout for Nano Banana image generation calls.

    Returns:
        timeout (int): Timeout in seconds
    """
    override = os.environ.get("CGCP_NANOBANANA2_TIMEOUT_SECONDS")
    if override:
        try:
            return max(30, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(30, int(json.load(file).get("nanobanana2_timeout_seconds", 120) or 120))

def _to_bool(value: object, default: bool = False) -> bool:
    """
    Coerces common textual values into bool.

    Args:
        value (object): Candidate value
        default (bool): Fallback value when empty/unknown

    Returns:
        parsed (bool): Parsed boolean
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default

def get_video_quality_mode() -> str:
    """
    Gets the video quality mode.

    Returns:
        mode (str): Quality mode ('standard' or 'hq_hybrid')
    """
    override = os.environ.get("CGCP_VIDEO_QUALITY_MODE", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("video_quality_mode", "hq_hybrid"))

def get_video_image_provider() -> str:
    """
    Gets the image generation provider used in the video pipeline.

    Returns:
        provider (str): 'gemini' or 'fal'
    """
    override = os.environ.get("CGCP_VIDEO_IMAGE_PROVIDER", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("video_image_provider", "gemini")).strip()

def get_video_motion_provider() -> str:
    """
    Gets the motion generation provider used in the video pipeline.

    Returns:
        provider (str): 'gemini_veo31', 'fal_veo3', or 'none'
    """
    override = os.environ.get("CGCP_VIDEO_MOTION_PROVIDER", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("video_motion_provider", "gemini_veo31")).strip()

def get_fal_api_key() -> str:
    """
    Gets the fal API key.

    Returns:
        key (str): API key
    """
    env_key = os.environ.get("FAL_KEY", "").strip()
    if env_key:
        return env_key
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_api_key", "")).strip()

def get_fal_image_model() -> str:
    """
    Gets the fal image model.

    Returns:
        model (str): fal model id
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_image_model", "fal-ai/nano-banana-pro")).strip()

def get_fal_image_size() -> str:
    """
    Gets the fal image size enum.

    Returns:
        image_size (str): Image size enum
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_image_size", "portrait_16_9")).strip()

def get_fal_enable_veo_motion() -> bool:
    """
    Gets whether Veo image-to-video enhancement is enabled.

    Returns:
        enabled (bool): True when enabled
    """
    override = os.environ.get("CGCP_ENABLE_VEO_MOTION")
    if override is not None:
        return _to_bool(override, default=False)
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        payload = json.load(file)
        if "video_enable_motion" in payload:
            return _to_bool(payload.get("video_enable_motion"), default=False)
        return _to_bool(payload.get("fal_enable_veo_motion", False), default=False)

def get_fal_veo_model() -> str:
    """
    Gets the fal Veo image-to-video model.

    Returns:
        model (str): fal model id
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_veo_model", "fal-ai/veo3/image-to-video")).strip()

def get_fal_veo_duration() -> str:
    """
    Gets Veo clip duration.

    Returns:
        duration (str): Duration enum (e.g. '4s', '6s', '8s')
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_veo_duration", "4s")).strip()

def get_fal_veo_resolution() -> str:
    """
    Gets Veo resolution.

    Returns:
        resolution (str): Resolution enum
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("fal_veo_resolution", "1080p")).strip()

def get_fal_veo_generate_audio() -> bool:
    """
    Gets whether Veo should generate native audio.

    Returns:
        enabled (bool): True when enabled
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return _to_bool(json.load(file).get("fal_veo_generate_audio", False), default=False)

def get_fal_motion_clip_limit() -> int:
    """
    Gets the max number of Veo motion clips to generate per short.

    Returns:
        limit (int): Max motion clips
    """
    override = os.environ.get("CGCP_FAL_MOTION_CLIP_LIMIT")
    if override:
        try:
            return max(0, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(0, int(json.load(file).get("fal_motion_clip_limit", 2) or 2))

def get_fal_client_timeout() -> int:
    """
    Gets fal client timeout in seconds.

    Returns:
        timeout (int): Timeout seconds
    """
    override = os.environ.get("CGCP_FAL_CLIENT_TIMEOUT")
    if override:
        try:
            return max(60, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(60, int(json.load(file).get("fal_client_timeout", 900) or 900))

def get_gemini_veo_model() -> str:
    """
    Gets the Gemini Veo model id.

    Returns:
        model (str): Model id
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("gemini_veo_model", "veo-3.1-fast-generate-preview")).strip()

def get_gemini_veo_duration_seconds() -> int:
    """
    Gets the Gemini Veo clip duration in seconds.

    Returns:
        duration (int): 4, 6, or 8
    """
    override = os.environ.get("CGCP_GEMINI_VEO_DURATION_SECONDS")
    if override:
        try:
            return int(override)
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return int(json.load(file).get("gemini_veo_duration_seconds", 4) or 4)

def get_gemini_veo_resolution() -> str:
    """
    Gets the Gemini Veo output resolution.

    Returns:
        resolution (str): 720p, 1080p, or 4k
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("gemini_veo_resolution", "720p")).strip()

def get_gemini_veo_aspect_ratio() -> str:
    """
    Gets the Gemini Veo output aspect ratio.

    Returns:
        ratio (str): 16:9 or 9:16
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("gemini_veo_aspect_ratio", "9:16")).strip()

def get_gemini_veo_timeout_seconds() -> int:
    """
    Gets the maximum wait time for a Gemini Veo operation.

    Returns:
        timeout (int): Seconds
    """
    override = os.environ.get("CGCP_GEMINI_VEO_TIMEOUT_SECONDS")
    if override:
        try:
            return max(60, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(60, int(json.load(file).get("gemini_veo_timeout_seconds", 900) or 900))

def get_gemini_veo_poll_interval_seconds() -> int:
    """
    Gets how often to poll Gemini Veo operations.

    Returns:
        interval (int): Seconds
    """
    override = os.environ.get("CGCP_GEMINI_VEO_POLL_INTERVAL_SECONDS")
    if override:
        try:
            return max(3, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(3, int(json.load(file).get("gemini_veo_poll_interval_seconds", 10) or 10))

def get_gemini_veo_download_timeout_seconds() -> int:
    """
    Gets the maximum download time for large Veo output files.

    Returns:
        timeout (int): Timeout in seconds
    """
    override = os.environ.get("CGCP_GEMINI_VEO_DOWNLOAD_TIMEOUT_SECONDS")
    if override:
        try:
            return max(120, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(120, int(json.load(file).get("gemini_veo_download_timeout_seconds", 1800) or 1800))

def get_video_download_stall_timeout_seconds() -> int:
    """
    Gets the maximum allowed period without file size growth while downloading video assets.

    Returns:
        timeout (int): Stall timeout in seconds
    """
    override = os.environ.get("CGCP_VIDEO_DOWNLOAD_STALL_TIMEOUT_SECONDS")
    if override:
        try:
            return max(30, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(30, int(json.load(file).get("video_download_stall_timeout_seconds", 180) or 180))

def get_video_subtitle_y() -> int:
    """
    Gets subtitle Y anchor position in vertical frame.

    Returns:
        y (int): Subtitle Y
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return int(json.load(file).get("video_subtitle_y", 1520))

def get_video_hook_y() -> int:
    """
    Gets hook text Y anchor position in vertical frame.

    Returns:
        y (int): Hook Y
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return int(json.load(file).get("video_hook_y", 64))

def get_threads() -> int:
    """
    Gets the amount of threads to use for example when writing to a file with MoviePy.

    Returns:
        threads (int): Amount of threads
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["threads"]
    
def get_zip_url() -> str:
    """
    Gets the URL to the zip file containing the songs.

    Returns:
        url (str): The URL to the zip file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["zip_url"]

def get_is_for_kids() -> bool:
    """
    Gets the is for kids flag from the config file.

    Returns:
        is_for_kids (bool): The is for kids flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["is_for_kids"]

def get_google_maps_scraper_zip_url() -> str:
    """
    Gets the URL to the zip file containing the Google Maps scraper.

    Returns:
        url (str): The URL to the zip file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["google_maps_scraper"]

def get_google_maps_scraper_niche() -> str:
    """
    Gets the niche for the Google Maps scraper.

    Returns:
        niche (str): The niche
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["google_maps_scraper_niche"]

def get_google_maps_scraper_niches() -> list[str]:
    """
    Gets one or more niches for the Google Maps scraper.

    Returns:
        niches (list[str]): The parsed niche list
    """
    raw = os.environ.get("CGCP_OUTREACH_NICHES")
    if raw is None:
        job_params = get_job_parameters()
        raw = job_params.get("niches") or job_params.get("niche") or get_google_maps_scraper_niche()

    if isinstance(raw, list):
        raw = "\n".join(str(item) for item in raw)
    else:
        raw = str(raw)

    parts: list[str] = []
    for chunk in raw.replace("\r", "\n").replace(";", "\n").split("\n"):
        for item in chunk.split(","):
            cleaned = item.strip()
            if cleaned:
                parts.append(cleaned)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in parts:
        lowered = item.lower()
        if lowered not in seen:
            seen.add(lowered)
            deduped.append(item)

    return deduped

def get_scraper_timeout() -> int:
    """
    Gets the timeout for the scraper.

    Returns:
        timeout (int): The timeout
    """
    override = os.environ.get("CGCP_OUTREACH_TIMEOUT")
    if override:
        try:
            return int(override)
        except ValueError:
            pass

    job_timeout = get_job_parameters().get("timeoutSeconds")
    if job_timeout is not None:
        try:
            return int(job_timeout)
        except (TypeError, ValueError):
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["scraper_timeout"] or 300

def get_scraper_depth() -> int:
    """
    Gets the search depth for the Google Maps scraper.

    Returns:
        depth (int): The scraper depth
    """
    override = os.environ.get("CGCP_OUTREACH_DEPTH")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass

    job_depth = get_job_parameters().get("depth")
    if job_depth is not None:
        try:
            return max(1, int(job_depth))
        except (TypeError, ValueError):
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(1, int(json.load(file).get("scraper_depth", 1) or 1))

def get_scraper_concurrency() -> int:
    """
    Gets the concurrency for the Google Maps scraper.

    Returns:
        concurrency (int): The scraper concurrency
    """
    override = os.environ.get("CGCP_OUTREACH_CONCURRENCY")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass

    job_concurrency = get_job_parameters().get("concurrency")
    if job_concurrency is not None:
        try:
            return max(1, int(job_concurrency))
        except (TypeError, ValueError):
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(1, int(json.load(file).get("scraper_concurrency", 1) or 1))

def get_scraper_exit_on_inactivity() -> str:
    """
    Gets the inactivity timeout string passed to the Google Maps scraper.

    Returns:
        duration (str): Duration string such as '90s'
    """
    override = os.environ.get("CGCP_OUTREACH_EXIT_ON_INACTIVITY", "").strip()
    if override:
        return override

    job_value = str(get_job_parameters().get("exitOnInactivity", "")).strip()
    if job_value:
        return job_value

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("scraper_exit_on_inactivity", "90s")).strip() or "90s"

def get_outreach_dry_run() -> bool:
    """
    Checks whether outreach should avoid sending live email.

    Returns:
        dry_run (bool): True if outreach should not send email
    """
    raw = os.environ.get("CGCP_OUTREACH_DRY_RUN", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True

    job_params = get_job_parameters()
    mode = str(job_params.get("mode", "")).strip().lower()
    if mode == "dry-run":
        return True

    dry_run_value = str(job_params.get("dryRun", "")).strip().lower()
    return dry_run_value in {"1", "true", "yes", "on"}

def get_outreach_max_emails() -> int:
    """
    Gets the per-run email send cap for outreach live runs.

    Returns:
        max_emails (int): Number of emails allowed for the run
    """
    env_value = os.environ.get("CGCP_OUTREACH_MAX_EMAILS")
    if env_value:
        try:
            return max(0, int(env_value))
        except ValueError:
            pass

    job_value = get_job_parameters().get("maxEmails")
    if job_value is not None:
        try:
            return max(0, int(job_value))
        except (TypeError, ValueError):
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(0, int(json.load(file).get("outreach_max_emails_per_run", 10) or 10))

def get_outreach_message_subject() -> str:
    """
    Gets the outreach message subject.

    Returns:
        subject (str): The outreach message subject
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["outreach_message_subject"]
    
def get_outreach_message_body_file() -> str:
    """
    Gets the outreach message body file.

    Returns:
        file (str): The outreach message body file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["outreach_message_body_file"]

def get_tts_voice() -> str:
    """
    Gets the TTS voice from the config file.

    Returns:
        voice (str): The TTS voice
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("tts_voice", "Jasper")

def get_tts_provider() -> str:
    """
    Gets the preferred TTS provider.

    Returns:
        provider (str): 'auto', 'openai', or 'edge'
    """
    override = os.environ.get("CGCP_TTS_PROVIDER", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("tts_provider", "auto")).strip()

def get_tts_openai_model() -> str:
    """
    Gets the OpenAI TTS model.

    Returns:
        model (str): OpenAI TTS model id
    """
    override = os.environ.get("CGCP_TTS_OPENAI_MODEL", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("tts_openai_model", "gpt-4o-mini-tts")).strip()

def get_tts_openai_voice() -> str:
    """
    Gets the OpenAI TTS voice.

    Returns:
        voice (str): OpenAI voice id
    """
    override = os.environ.get("CGCP_TTS_OPENAI_VOICE", "").strip()
    if override:
        return override
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("tts_openai_voice", "verse")).strip()

def get_tts_openai_speed() -> float:
    """
    Gets OpenAI TTS speed multiplier.

    Returns:
        speed (float): Speech speed multiplier
    """
    override = os.environ.get("CGCP_TTS_OPENAI_SPEED", "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        raw = json.load(file).get("tts_openai_speed", 1.0)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 1.0

def get_tts_openai_instructions() -> str:
    """
    Gets OpenAI TTS speaking instructions.

    Returns:
        instructions (str): Prompt instructions for voice style
    """
    default_instructions = (
        "Speak naturally like a real person with warm, expressive pacing. "
        "Handle Filipino and English code-switching smoothly, with clear pronunciation "
        "and natural sentence rhythm. Avoid robotic cadence."
    )
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("tts_openai_instructions", default_instructions)).strip()

def get_openai_api_key() -> str:
    """
    Gets OpenAI API key.

    Returns:
        key (str): API key
    """
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("openai_api_key", "")).strip()

def get_youtube_upload_confirm_timeout_seconds() -> int:
    """
    Gets timeout used to verify uploaded videos in YouTube Studio.

    Returns:
        timeout (int): Timeout seconds
    """
    override = os.environ.get("CGCP_YOUTUBE_UPLOAD_CONFIRM_TIMEOUT_SECONDS", "").strip()
    if override:
        try:
            return max(60, int(override))
        except ValueError:
            pass
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(60, int(json.load(file).get("youtube_upload_confirm_timeout_seconds", 420) or 420))

def get_assemblyai_api_key() -> str:
    """
    Gets the AssemblyAI API key.

    Returns:
        key (str): The AssemblyAI API key
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["assembly_ai_api_key"]

def get_stt_provider() -> str:
    """
    Gets the configured STT provider.

    Returns:
        provider (str): The STT provider
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("stt_provider", "local_whisper")

def get_whisper_model() -> str:
    """
    Gets the local Whisper model name.

    Returns:
        model (str): Whisper model name
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_model", "base")

def get_whisper_device() -> str:
    """
    Gets the target device for Whisper inference.

    Returns:
        device (str): Whisper device
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_device", "auto")

def get_whisper_compute_type() -> str:
    """
    Gets the compute type for Whisper inference.

    Returns:
        compute_type (str): Whisper compute type
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_compute_type", "int8")
    
def equalize_subtitles(srt_path: str, max_chars: int = 10) -> None:
    """
    Equalizes the subtitles in a SRT file.

    Args:
        srt_path (str): The path to the SRT file
        max_chars (int): The maximum amount of characters in a subtitle

    Returns:
        None
    """
    srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)
    
def get_font() -> str:
    """
    Gets the font from the config file.

    Returns:
        font (str): The font
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["font"]

def get_fonts_dir() -> str:
    """
    Gets the fonts directory.

    Returns:
        dir (str): The fonts directory
    """
    return os.path.join(ROOT_DIR, "fonts")

def get_imagemagick_path() -> str:
    """
    Gets the path to ImageMagick.

    Returns:
        path (str): The path to ImageMagick
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["imagemagick_path"]

def get_script_sentence_length() -> int:
    """
    Gets the forced script's sentence length.
    In case there is no sentence length in config, returns 4 when none

    Returns:
        length (int): Length of script's sentence
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)
        if (config_json.get("script_sentence_length") is not None):
            return config_json["script_sentence_length"]
        else:
            return 4

def get_youtube_image_prompt_max_count() -> int:
    """
    Gets max image prompt count per YouTube short.

    Returns:
        count (int): Max prompt count
    """
    override = os.environ.get("CGCP_YOUTUBE_IMAGE_PROMPT_MAX_COUNT")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(1, int(json.load(file).get("youtube_image_prompt_max_count", 8) or 8))

def get_youtube_max_short_duration_seconds() -> int:
    """
    Gets maximum allowed duration for generated YouTube shorts.

    Returns:
        seconds (int): Max duration in seconds
    """
    override = os.environ.get("CGCP_YOUTUBE_MAX_SHORT_DURATION_SECONDS")
    if override:
        try:
            return max(15, int(override))
        except ValueError:
            pass

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return max(15, int(json.load(file).get("youtube_max_short_duration_seconds", 60) or 60))

def get_youtube_script_language() -> str:
    """
    Gets forced script language for YouTube generation.

    Returns:
        language (str): Script language (e.g. 'Filipino')
    """
    override = os.environ.get("CGCP_YOUTUBE_SCRIPT_LANGUAGE", "").strip()
    if override:
        return override

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("youtube_script_language", "")).strip()

def get_youtube_subtitle_source() -> str:
    """
    Gets subtitle generation source for YouTube shorts.

    Returns:
        source (str): 'script' or 'stt'
    """
    override = os.environ.get("CGCP_YOUTUBE_SUBTITLE_SOURCE", "").strip().lower()
    if override in {"script", "stt"}:
        return override

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = str(json.load(file).get("youtube_subtitle_source", "script")).strip().lower()
        return configured if configured in {"script", "stt"} else "script"

