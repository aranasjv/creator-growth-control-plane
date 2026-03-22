import os
import json

from typing import List
from config import ROOT_DIR


def _ensure_cache_dir_exists() -> None:
    """
    Ensures the .mp cache directory exists.

    Returns:
        None
    """
    os.makedirs(get_cache_path(), exist_ok=True)


def _write_json(path: str, payload: dict) -> None:
    """
    Writes JSON payloads with stable UTF-8 encoding.

    Args:
        path (str): Target file path
        payload (dict): JSON-serializable dictionary

    Returns:
        None
    """
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)


def _read_json_or_default(path: str, default_payload: dict) -> dict:
    """
    Reads a JSON file and falls back to a default payload when the file is
    missing or malformed. The reader accepts UTF-8 BOM for Windows-written files.

    Args:
        path (str): Source file path
        default_payload (dict): Default JSON content when read fails

    Returns:
        parsed (dict): Parsed JSON object
    """
    if not os.path.exists(path):
        _write_json(path, default_payload)
        return default_payload

    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            parsed = json.load(file)
            return parsed if isinstance(parsed, dict) else default_payload
    except (json.JSONDecodeError, OSError):
        _write_json(path, default_payload)
        return default_payload

def get_cache_path() -> str:
    """
    Gets the path to the cache file.

    Returns:
        path (str): The path to the cache folder
    """
    return os.path.join(ROOT_DIR, '.mp')

def get_afm_cache_path() -> str:
    """
    Gets the path to the Affiliate Marketing cache file.

    Returns:
        path (str): The path to the AFM cache folder
    """
    return os.path.join(get_cache_path(), 'afm.json')

def get_twitter_cache_path() -> str:
    """
    Gets the path to the Twitter cache file.

    Returns:
        path (str): The path to the Twitter cache folder
    """
    return os.path.join(get_cache_path(), 'twitter.json')

def get_youtube_cache_path() -> str:
    """
    Gets the path to the YouTube cache file.

    Returns:
        path (str): The path to the YouTube cache folder
    """
    return os.path.join(get_cache_path(), 'youtube.json')

def get_provider_cache_path(provider: str) -> str:
    """
    Gets the cache path for a supported account provider.

    Args:
        provider (str): The provider name ("twitter" or "youtube")

    Returns:
        path (str): The provider-specific cache path

    Raises:
        ValueError: If the provider is unsupported
    """
    if provider == "twitter":
        return get_twitter_cache_path()
    if provider == "youtube":
        return get_youtube_cache_path()

    raise ValueError(f"Unsupported provider '{provider}'. Expected 'twitter' or 'youtube'.")

def get_accounts(provider: str) -> List[dict]:
    """
    Gets the accounts from the cache.

    Args:
        provider (str): The provider to get the accounts for

    Returns:
        account (List[dict]): The accounts
    """
    cache_path = get_provider_cache_path(provider)
    _ensure_cache_dir_exists()
    parsed = _read_json_or_default(cache_path, {"accounts": []})
    accounts = parsed.get("accounts", [])
    return accounts if isinstance(accounts, list) else []

def add_account(provider: str, account: dict) -> None:
    """
    Adds an account to the cache.

    Args:
        provider (str): The provider to add the account to ("twitter" or "youtube")
        account (dict): The account to add

    Returns:
        None
    """
    cache_path = get_provider_cache_path(provider)

    # Get the current accounts
    accounts = get_accounts(provider)

    # Add the new account
    accounts.append(account)

    # Write the new accounts to the cache
    _write_json(cache_path, {"accounts": accounts})

def remove_account(provider: str, account_id: str) -> None:
    """
    Removes an account from the cache.

    Args:
        provider (str): The provider to remove the account from ("twitter" or "youtube")
        account_id (str): The ID of the account to remove

    Returns:
        None
    """
    # Get the current accounts
    accounts = get_accounts(provider)

    # Remove the account
    accounts = [account for account in accounts if account['id'] != account_id]

    # Write the new accounts to the cache
    cache_path = get_provider_cache_path(provider)
    _write_json(cache_path, {"accounts": accounts})

def get_products() -> List[dict]:
    """
    Gets the products from the cache.

    Returns:
        products (List[dict]): The products
    """
    _ensure_cache_dir_exists()
    parsed = _read_json_or_default(get_afm_cache_path(), {"products": []})
    products = parsed.get("products", [])
    return products if isinstance(products, list) else []
    
def add_product(product: dict) -> None:
    """
    Adds a product to the cache.

    Args:
        product (dict): The product to add

    Returns:
        None
    """
    # Get the current products
    products = get_products()

    # Add the new product
    products.append(product)

    # Write the new products to the cache
    _write_json(get_afm_cache_path(), {"products": products})
    
def get_results_cache_path() -> str:
    """
    Gets the path to the results cache file.

    Returns:
        path (str): The path to the results cache folder
    """
    return os.path.join(get_cache_path(), 'scraper_results.csv')
