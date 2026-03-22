#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, Tuple

import requests


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"
TARGET_CHOICES = ("twitter", "youtube", "affiliate", "outreach")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def check_url(url: str, timeout: int = 3) -> Tuple[bool, str]:
    try:
        response = requests.get(url, timeout=timeout)
        return True, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def parse_targets(raw_targets: Iterable[str]) -> list[str]:
    selected = [target.lower() for target in raw_targets]
    if not selected or "all" in selected:
        return list(TARGET_CHOICES)

    invalid = sorted(set(selected) - set(TARGET_CHOICES))
    if invalid:
        raise ValueError(f"Unsupported targets: {', '.join(invalid)}")

    return list(dict.fromkeys(selected))


def requires_browser_profile(targets: Iterable[str]) -> bool:
    return any(target in {"twitter", "youtube", "affiliate"} for target in targets)


def requires_ollama(targets: Iterable[str]) -> bool:
    return any(target in {"twitter", "youtube", "affiliate"} for target in targets)


def requires_nanobanana(targets: Iterable[str]) -> bool:
    return "youtube" in targets


def requires_imagemagick(targets: Iterable[str]) -> bool:
    return "youtube" in targets


def requires_go(targets: Iterable[str]) -> bool:
    return "outreach" in targets


def command_exists(command_name: str, extra_paths: Iterable[str] | None = None) -> bool:
    if shutil.which(command_name):
        return True

    for candidate in extra_paths or []:
        if candidate and os.path.exists(candidate):
            return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local desktop readiness for Creator Growth Control Plane.")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["all"],
        help="Which flows to validate: all, twitter, youtube, affiliate, outreach.",
    )
    args = parser.parse_args()

    try:
        targets = parse_targets(args.targets)
    except ValueError as exc:
        fail(str(exc))
        return 1

    ok(f"targets={', '.join(targets)}")

    if not CONFIG_PATH.exists():
        fail(f"Missing config file: {CONFIG_PATH}")
        return 1

    with CONFIG_PATH.open("r", encoding="utf-8-sig") as handle:
        cfg = json.load(handle)

    failures = 0

    stt_provider = str(cfg.get("stt_provider", "local_whisper")).lower()
    ok(f"stt_provider={stt_provider}")

    imagemagick_path = str(cfg.get("imagemagick_path", "")).strip()
    imagemagick_ok = bool(imagemagick_path and os.path.exists(imagemagick_path))
    if imagemagick_ok:
        ok(f"imagemagick_path exists: {imagemagick_path}")
    elif requires_imagemagick(targets):
        fail(
            "imagemagick_path is not set to a valid executable path. "
            "YouTube video rendering requires ImageMagick."
        )
        failures += 1
    else:
        warn(
            "imagemagick_path is not set to a valid executable path. "
            "That only blocks the YouTube flow."
        )

    firefox_profile = str(cfg.get("firefox_profile", "")).strip()
    firefox_ok = bool(firefox_profile and os.path.isdir(firefox_profile))
    if firefox_ok:
        ok(f"firefox_profile exists: {firefox_profile}")
    elif requires_browser_profile(targets):
        fail(
            "firefox_profile is empty or invalid. "
            "Twitter, YouTube, and affiliate automation require a logged-in Firefox profile."
        )
        failures += 1
    else:
        warn("firefox_profile is empty. That only blocks browser-driven flows.")

    ollama_base = str(cfg.get("ollama_base_url", "http://127.0.0.1:11434")).rstrip("/")
    ollama_ok, ollama_detail = check_url(f"{ollama_base}/api/tags")
    if ollama_ok:
        ok(f"Ollama reachable at {ollama_base}")
        try:
            tags = requests.get(f"{ollama_base}/api/tags", timeout=5).json()
            models = [model.get("name") for model in tags.get("models", []) if model.get("name")]
            if models:
                ok(f"Ollama models available: {', '.join(models[:10])}")
            elif requires_ollama(targets):
                fail("No models found on Ollama. Pull a model first (for example 'ollama pull llama3.2:3b').")
                failures += 1
            else:
                warn("No models found on Ollama. That blocks text-generation flows.")
        except Exception as exc:
            warn(f"Could not validate Ollama model list: {exc}")
    elif requires_ollama(targets):
        fail(f"Ollama is not reachable at {ollama_base}: {ollama_detail}")
        failures += 1
    else:
        warn(f"Ollama is not reachable at {ollama_base}. That blocks text-generation flows.")

    nanobanana_key = str(cfg.get("nanobanana2_api_key", "") or os.environ.get("GEMINI_API_KEY", "")).strip()
    nanobanana_base = str(
        cfg.get("nanobanana2_api_base_url", "https://generativelanguage.googleapis.com/v1beta")
    ).rstrip("/")
    if nanobanana_key:
        ok("nanobanana2_api_key is set")
    elif requires_nanobanana(targets):
        fail("nanobanana2_api_key is empty (and GEMINI_API_KEY is not set). The YouTube flow needs it.")
        failures += 1
    else:
        warn("nanobanana2_api_key is empty. That only blocks the YouTube flow.")

    nanobanana_ok, nanobanana_detail = check_url(nanobanana_base, timeout=8)
    if nanobanana_ok:
        ok(f"Nano Banana 2 base URL reachable: {nanobanana_base}")
    else:
        warn(f"Nano Banana 2 base URL could not be reached: {nanobanana_detail}")

    if stt_provider == "local_whisper":
        try:
            import faster_whisper  # noqa: F401

            ok("faster-whisper is installed")
        except Exception as exc:
            fail(f"faster-whisper is not importable: {exc}")
            failures += 1

    if requires_go(targets):
        if command_exists("go", [r"C:\Program Files\Go\bin\go.exe"]):
            ok("Go is installed")
        else:
            fail("Go is not installed. The outreach scraper build requires it.")
            failures += 1

        email_cfg = cfg.get("email", {})
        if email_cfg.get("username") and email_cfg.get("password"):
            ok("SMTP credentials are configured")
        else:
            fail("SMTP credentials are missing. Outreach needs email.username and email.password.")
            failures += 1

        niche = str(cfg.get("google_maps_scraper_niche", "")).strip()
        niche_items = [
            item.strip()
            for block in niche.replace("\r", "\n").replace(";", "\n").split("\n")
            for item in block.split(",")
            if item.strip()
        ]
        if niche_items:
            ok(f"google_maps_scraper_niche is configured with {len(niche_items)} niche target(s)")
        else:
            fail("google_maps_scraper_niche is empty. Outreach needs a niche to scrape.")
            failures += 1

        body_file = ROOT_DIR / str(cfg.get("outreach_message_body_file", "")).strip()
        if body_file.exists():
            ok(f"outreach_message_body_file exists: {body_file.name}")
        else:
            fail(f"outreach_message_body_file is missing: {body_file}")
            failures += 1

    print("")
    if failures:
        print(f"Preflight completed with {failures} blocking issue(s) for targets: {', '.join(targets)}.")
        return 1

    print(f"Preflight passed for targets: {', '.join(targets)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
