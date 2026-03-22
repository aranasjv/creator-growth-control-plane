import os
import requests
import json
import logging
import traceback
import redis
from typing import Dict, List, Any

API_BASE = os.environ.get("NEXT_PUBLIC_API_BASE_URL", "http://localhost:5050").rstrip("/")
REDIS_URL = os.environ.get("CGCP_REDIS_URL", "redis://localhost:6379/0")

# Setup redis client
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

DEFAULT_MODEL_CATALOG: Dict[str, List[str]] = {
    "ollama": [
        "llama3.2:3b",
        "llama3.2:1b",
        "qwen2.5:7b",
        "mistral:7b",
        "gemma2:9b",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o",
    ],
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    ],
}

def get_settings() -> Dict[str, Any]:
    try:
        if redis_client.exists("cgcp:settings"):
            data = redis_client.get("cgcp:settings")
            if data:
                return json.loads(data)
    except Exception as e:
        print(f"Redis cache miss/error for settings: {e}")

    try:
        r = requests.get(f"{API_BASE}/api/settings", timeout=10)
        if r.status_code == 200:
            data = r.json()
            try:
                redis_client.setex("cgcp:settings", 3600, json.dumps(data))
            except Exception:
                pass
            return data
    except Exception as e:
        print(f"Warning: Failed to fetch settings: {e}")
    return {}

def get_prompts() -> List[Dict[str, Any]]:
    try:
        if redis_client.exists("cgcp:prompts"):
            data = redis_client.get("cgcp:prompts")
            if data:
                return json.loads(data)
    except Exception as e:
        print(f"Redis cache miss/error for prompts: {e}")

    try:
        r = requests.get(f"{API_BASE}/api/prompts", timeout=10)
        if r.status_code == 200:
            data = r.json()
            try:
                redis_client.setex("cgcp:prompts", 3600, json.dumps(data))
            except Exception:
                pass
            return data
    except Exception as e:
        print(f"Warning: Failed to fetch prompts: {e}")
    return []

def get_managed_prompt(key: str, default_prompt: str = "", **kwargs) -> str:
    prompts = get_prompts()
    for p in prompts:
        # Check both snake_case and PascalCase keys (from C# EF Core serialization)
        p_key = p.get("key") or p.get("Key")
        if p_key == key:
            text = str(p.get("promptText") or p.get("PromptText") or "")
            for k, v in kwargs.items():
                text = text.replace(f"{{{k}}}", str(v))
            return text
            
    # Fallback to default if not found
    text = default_prompt
    for k, v in kwargs.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text

_selected_model = None

def select_model(model_name: str):
    global _selected_model
    _selected_model = model_name


def _resolve_model_catalog(settings: Dict[str, Any]) -> Dict[str, List[str]]:
    raw_catalog = settings.get("modelCatalog") or settings.get("ModelCatalog") or {}
    if not isinstance(raw_catalog, dict):
        raw_catalog = {}

    resolved: Dict[str, List[str]] = {}
    for provider, defaults in DEFAULT_MODEL_CATALOG.items():
        configured = raw_catalog.get(provider)
        if isinstance(configured, list):
            cleaned = [str(item).strip() for item in configured if str(item).strip()]
            resolved[provider] = cleaned or defaults
        else:
            resolved[provider] = defaults
    return resolved


def _pick_known_model(provider: str, candidate: str | None, catalog: Dict[str, List[str]]) -> str:
    options = catalog.get(provider) or DEFAULT_MODEL_CATALOG[provider]
    lookup = (candidate or "").strip().lower()
    if lookup:
        for model in options:
            if model.lower() == lookup:
                return model
    return options[0]


def _normalize_model_for_provider(provider: str, requested_model: str | None, settings: Dict[str, Any]) -> str:
    catalog = _resolve_model_catalog(settings)
    model = (requested_model or "").strip()

    if provider == "openai":
        configured = str(
            settings.get("openAIModelName")
            or settings.get("OpenAIModelName")
            or settings.get("openAiModelName")
            or ""
        ).strip()
        return _pick_known_model("openai", model or configured, catalog)

    if provider == "gemini":
        configured = str(
            settings.get("geminiModelName")
            or settings.get("GeminiModelName")
            or ""
        ).strip()
        return _pick_known_model("gemini", model or configured, catalog)

    configured = str(settings.get("ollamaModelName") or settings.get("OllamaModelName") or "").strip()
    return _pick_known_model("ollama", model or configured, catalog)

def generate_text(prompt: str, model_name: str = None) -> str:
    settings = get_settings()
    provider = str(settings.get("activeModelProvider") or settings.get("ActiveModelProvider") or "ollama").lower()
    model = _normalize_model_for_provider(provider, model_name or _selected_model, settings)

    if provider == "openai":
        import openai
        api_key = settings.get("openAIApiKey") or settings.get("OpenAIApiKey")
        if not api_key:
            raise ValueError("OpenAI API key not configured in settings.")
        
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    elif provider == "gemini":
        import google.generativeai as genai
        api_key = settings.get("geminiApiKey") or settings.get("GeminiApiKey")
        if not api_key:
            raise ValueError("Gemini API key not configured in settings.")
        
        genai.configure(api_key=api_key)
        generative_model = genai.GenerativeModel(model)
        
        response = generative_model.generate_content(prompt)
        return response.text

    else:
        # Fall back to ollama
        import ollama
        try:
            response = ollama.generate(model=model, prompt=prompt)
            return response['response']
        except Exception as e:
            print(f"Ollama generation failed: {e}")
            traceback.print_exc()
            return ""
