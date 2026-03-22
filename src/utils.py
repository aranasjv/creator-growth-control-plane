import os
import random
import zipfile
import requests
import platform
import math
import struct
import wave
import shutil
from uuid import uuid4

from status import *
from config import *

DEFAULT_SONG_ARCHIVE_URLS = []


def prepare_firefox_profile(profile_path: str) -> tuple[str, str | None]:
    """
    Prepares a Firefox profile path for Selenium use.
    By default this creates a temporary clone to avoid profile lock contention.

    Args:
        profile_path (str): Original Firefox profile directory

    Returns:
        tuple[str, str | None]: (path_to_use, temporary_clone_path_or_none)
    """
    clone_flag = os.environ.get("CGCP_CLONE_FIREFOX_PROFILE", "1").strip().lower()
    use_clone = clone_flag not in {"0", "false", "no", "off"}

    if not use_clone:
        return profile_path, None

    clone_root = os.path.join(ROOT_DIR, ".mp", "firefox_profile_clones")
    os.makedirs(clone_root, exist_ok=True)
    clone_path = os.path.join(clone_root, str(uuid4()))
    ignore_patterns = shutil.ignore_patterns(
        "parent.lock",
        "lock",
        ".parentlock",
        "*.lock",
        "Singleton*",
    )

    shutil.copytree(profile_path, clone_path, ignore=ignore_patterns)

    for lock_name in ("parent.lock", "lock", ".parentlock"):
        lock_path = os.path.join(clone_path, lock_name)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

    return clone_path, clone_path


def cleanup_firefox_profile_clone(clone_path: str | None) -> None:
    """
    Removes a temporary Firefox profile clone created for Selenium.

    Args:
        clone_path (str | None): Clone path

    Returns:
        None
    """
    if not clone_path:
        return

    if os.path.isdir(clone_path):
        shutil.rmtree(clone_path, ignore_errors=True)


def _write_fallback_song(target_path: str, duration_seconds: float = 2.0) -> None:
    """
    Writes a small local WAV tone used when no songs are available.

    Args:
        target_path (str): Destination WAV path
        duration_seconds (float): Tone duration

    Returns:
        None
    """
    sample_rate = 44100
    frequency_hz = 440.0
    amplitude = 0.20
    total_samples = int(sample_rate * max(duration_seconds, 0.5))

    with wave.open(target_path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for idx in range(total_samples):
            sample = int(
                amplitude
                * 32767.0
                * math.sin(2.0 * math.pi * frequency_hz * (idx / sample_rate))
            )
            wav_file.writeframesraw(struct.pack("<h", sample))


def close_running_selenium_instances() -> None:
    """
    Closes any running Selenium instances.

    Returns:
        None
    """
    try:
        info(" => Closing running Selenium instances...")

        # Kill all running Firefox instances
        if platform.system() == "Windows":
            os.system("taskkill /f /im firefox.exe")
        else:
            os.system("pkill firefox")

        success(" => Closed running Selenium instances.")

    except Exception as e:
        error(f"Error occurred while closing running Selenium instances: {str(e)}")


def build_url(youtube_video_id: str) -> str:
    """
    Builds the URL to the YouTube video.

    Args:
        youtube_video_id (str): The YouTube video ID.

    Returns:
        url (str): The URL to the YouTube video.
    """
    return f"https://www.youtube.com/watch?v={youtube_video_id}"


def rem_temp_files() -> None:
    """
    Removes temporary files in the `.mp` directory.

    Returns:
        None
    """
    # Path to the `.mp` directory
    mp_dir = os.path.join(ROOT_DIR, ".mp")

    files = os.listdir(mp_dir)

    for file in files:
        if not file.endswith(".json"):
            os.remove(os.path.join(mp_dir, file))


def fetch_songs() -> None:
    """
    Downloads songs into songs/ directory to use with geneated videos.

    Returns:
        None
    """
    try:
        info(f" => Fetching songs...")

        files_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(files_dir):
            os.mkdir(files_dir)
            if get_verbose():
                info(f" => Created directory: {files_dir}")
        else:
            existing_audio_files = [
                name
                for name in os.listdir(files_dir)
                if os.path.isfile(os.path.join(files_dir, name))
                and name.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
            ]
            if len(existing_audio_files) > 0:
                return

        configured_url = get_zip_url().strip()
        download_urls = [configured_url] if configured_url else []
        download_urls.extend(DEFAULT_SONG_ARCHIVE_URLS)

        archive_path = os.path.join(files_dir, "songs.zip")
        downloaded = False

        for download_url in download_urls:
            try:
                response = requests.get(download_url, timeout=60)
                response.raise_for_status()

                with open(archive_path, "wb") as file:
                    file.write(response.content)

                SAFE_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if not basename or not basename.lower().endswith(SAFE_EXTENSIONS):
                            warning(f"Skipping non-audio file in archive: {member}")
                            continue
                        if ".." in member or member.startswith("/"):
                            warning(f"Skipping suspicious path in archive: {member}")
                            continue
                        zf.extract(member, files_dir)

                downloaded = True
                break
            except Exception as err:
                warning(f"Failed to fetch songs from {download_url}: {err}")

        if not downloaded:
            fallback_song_path = os.path.join(files_dir, "fallback-tone.wav")
            warning(
                "Could not download songs archive; generating local fallback background track."
            )
            _write_fallback_song(fallback_song_path)
            success(f' => Generated fallback song: "{fallback_song_path}"')
            return

        # Remove the zip file
        if os.path.exists(archive_path):
            os.remove(archive_path)

        success(" => Downloaded Songs to ../Songs.")

    except Exception as e:
        error(f"Error occurred while fetching songs: {str(e)}")


def choose_random_song() -> str:
    """
    Chooses a random song from the songs/ directory.

    Returns:
        str: The path to the chosen song.
    """
    try:
        songs_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(songs_dir):
            os.makedirs(songs_dir, exist_ok=True)

        songs = [
            name
            for name in os.listdir(songs_dir)
            if os.path.isfile(os.path.join(songs_dir, name))
            and name.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
        ]
        if len(songs) == 0:
            fallback_song_name = "fallback-tone.wav"
            fallback_song_path = os.path.join(songs_dir, fallback_song_name)
            _write_fallback_song(fallback_song_path)
            songs.append(fallback_song_name)

        song = random.choice(songs)
        success(f" => Chose song: {song}")
        return os.path.join(ROOT_DIR, "Songs", song)
    except Exception as e:
        error(f"Error occurred while choosing random song: {str(e)}")
        raise

