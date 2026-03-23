import argparse
import csv
import json
import os
import time

from cache import get_accounts, get_products, get_results_cache_path
from config import get_ollama_model, get_outreach_dry_run


def require_account(provider: str, account_id: str) -> dict:
    for account in get_accounts(provider):
        if account["id"] == account_id:
            return account
    raise ValueError(f"Could not find {provider} account '{account_id}'.")


def require_product(product_id: str) -> dict:
    for product in get_products():
        if product["id"] == product_id:
            return product
    raise ValueError(f"Could not find affiliate product '{product_id}'.")


def configure_model(model_name: str | None) -> str | None:
    selected = model_name or get_ollama_model() or None
    if selected:
        from llm_provider import select_model

        select_model(selected)
    return selected


def _as_bool(value: object, default: bool = False) -> bool:
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


def run_twitter(account_id: str) -> dict:
    from classes.Twitter import Twitter

    account = require_account("twitter", account_id)
    topic_seed = (account.get("topic") or account.get("niche") or "").strip()
    if not topic_seed:
        raise ValueError("Twitter account is missing both topic and niche.")

    twitter = Twitter(account["id"], account["nickname"], account["firefox_profile"], topic_seed)
    try:
        twitter.post()
    finally:
        try:
            twitter.quit()
        except Exception:
            pass
        time.sleep(2)

    return {
        "summary": f"Posted to X for {account['nickname']}.",
        "metrics": {"postsCreated": 1},
    }


def run_youtube(account_id: str) -> dict:
    from classes.Tts import TTS
    from classes.YouTube import YouTube
    from utils import fetch_songs

    account = require_account("youtube", account_id)
    topic_seed = (account.get("topic") or account.get("niche") or "").strip()
    if not topic_seed:
        raise ValueError("YouTube account is missing both topic and niche.")
    from config import get_job_parameters
    params = get_job_parameters()
    manual_topic = str(params.get("topic_override") or params.get("topic") or "").strip()
    forced_topic = manual_topic or topic_seed
    allow_topic_generation = _as_bool(params.get("allow_topic_generation"), default=False)
    longform_raw = str(params.get("longform_content") or "").strip()
    use_longform = _as_bool(params.get("use_longform"), default=bool(longform_raw))
    longform_content = longform_raw if use_longform and longform_raw else None

    fetch_songs()
    youtube = YouTube(
        account["id"],
        account["nickname"],
        account["firefox_profile"],
        topic_seed,
        account["language"],
        forced_topic=forced_topic,
        allow_topic_generation=allow_topic_generation,
    )

    try:
        tts = TTS()
        video_path = youtube.generate_video(tts, longform_content=longform_content)
        uploaded = youtube.upload_video()
        if not uploaded:
            reason = getattr(youtube, "last_upload_error", None) or "No additional details were reported."
            raise RuntimeError(f"YouTube upload reported failure: {reason}")
    finally:
        try:
            youtube.quit()
        except Exception:
            pass
        time.sleep(2)

    return {
        "summary": f"Generated and uploaded a short for {account['nickname']}.",
        "metrics": {"videosPublished": 1},
        "output": {"videoPath": os.path.abspath(video_path)},
    }


def run_afm(product_id: str) -> dict:
    from classes.AFM import AffiliateMarketing

    product = require_product(product_id)
    account = require_account("twitter", product["twitter_uuid"])
    afm = AffiliateMarketing(
        product["affiliate_link"],
        account["firefox_profile"],
        account["id"],
        account["nickname"],
        account["topic"],
    )
    try:
        pitch = afm.generate_pitch()
        afm.share_pitch("twitter")
    finally:
        try:
            afm.quit()
        except Exception:
            pass
        time.sleep(2)

    return {
        "summary": f"Generated affiliate pitch and shared it for {account['nickname']}.",
        "metrics": {"pitchesShared": 1},
        "output": {"pitchPreview": pitch[:180]},
    }


def run_outreach() -> dict:
    from classes.Outreach import Outreach

    outreach = Outreach()
    outreach_summary = outreach.start() or {}

    leads_scraped = int(outreach_summary.get("leadsScraped", 0) or 0)
    emails_prepared = int(outreach_summary.get("emailsPrepared", 0) or 0)
    emails_sent = int(outreach_summary.get("emailsSent", 0) or 0)
    emails_failed = int(outreach_summary.get("emailsFailed", 0) or 0)
    results_path = get_results_cache_path()
    if os.path.exists(results_path) and (leads_scraped == 0 or emails_prepared == 0):
        with open(results_path, "r", newline="", errors="ignore") as csv_file:
            reader = list(csv.reader(csv_file))
            if len(reader) > 1:
                if leads_scraped == 0:
                    leads_scraped = len(reader) - 1
                for row in reader[1:]:
                    if any("@" in column for column in row):
                        emails_prepared += 1

    dry_run = get_outreach_dry_run()

    if dry_run:
        emails_sent = 0

    return {
        "summary": "Completed outreach dry run." if dry_run else "Completed outreach run.",
        "metrics": {
            "leadsScraped": leads_scraped,
            "emailsPrepared": emails_prepared,
            "emailsSent": emails_sent,
            "emailsFailed": emails_failed,
        },
        "output": {
            "outreach": outreach_summary,
        },
    }


def run_smoke_test() -> dict:
    return {
        "summary": "Control plane queue round-trip completed.",
        "metrics": {"pipelineChecksPassed": 1},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Creator Growth Control Plane jobs in worker mode.")
    parser.add_argument("--job-type", required=True)
    parser.add_argument("--account-id")
    parser.add_argument("--product-id")
    parser.add_argument("--model")
    args = parser.parse_args()

    configure_model(args.model)

    if args.job_type == "twitter_post":
        if not args.account_id:
            raise ValueError("twitter_post requires --account-id")
        result = run_twitter(args.account_id)
    elif args.job_type == "youtube_upload":
        if not args.account_id:
            raise ValueError("youtube_upload requires --account-id")
        result = run_youtube(args.account_id)
    elif args.job_type == "afm_pitch":
        if not args.product_id:
            raise ValueError("afm_pitch requires --product-id")
        result = run_afm(args.product_id)
    elif args.job_type == "outreach_run":
        result = run_outreach()
    elif args.job_type == "smoke_test":
        result = run_smoke_test()
    else:
        raise ValueError(f"Unsupported job type: {args.job_type}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
