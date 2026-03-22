"""
Shared constants for CLI menu choices and UI automation selectors.

This module is imported by legacy automation flows (`main.py`, `AFM.py`,
`YouTube.py`). Keep these values stable and centrally managed.
"""

# Main CLI options
OPTIONS = [
    "Start YouTube Shorts Automater",
    "Start Twitter Bot",
    "Start Affiliate Marketing",
    "Start Outreach",
    "Quit",
]

# YouTube sub-menu options
YOUTUBE_OPTIONS = [
    "Generate video",
    "Get uploaded videos",
    "Set upload CRON job",
    "Back",
]

YOUTUBE_CRON_OPTIONS = [
    "Upload once per day",
    "Upload twice per day",
    "Back",
]

# Twitter sub-menu options
TWITTER_OPTIONS = [
    "Generate and post tweet",
    "Get posted tweets",
    "Set posting CRON job",
    "Back",
]

TWITTER_CRON_OPTIONS = [
    "Post once per day",
    "Post twice per day",
    "Post three times per day",
    "Back",
]

# Amazon selectors for affiliate scraping
AMAZON_PRODUCT_TITLE_ID = "productTitle"
AMAZON_FEATURE_BULLETS_ID = "feature-bullets"

# YouTube Studio selectors
YOUTUBE_MADE_FOR_KIDS_NAME = "VIDEO_MADE_FOR_KIDS_MFK"
YOUTUBE_NOT_MADE_FOR_KIDS_NAME = "VIDEO_MADE_FOR_KIDS_NOT_MFK"
YOUTUBE_NEXT_BUTTON_ID = "next-button"
YOUTUBE_DONE_BUTTON_ID = "done-button"
