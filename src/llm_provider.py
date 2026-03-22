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
        if p.get("key") == key:
            text = p.get("promptText", "")
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

def generate_text(prompt: str, model_name: str = None) -> str:
    settings = get_settings()
    provider = settings.get("activeModelProvider", "ollama").lower()
    
    # Determine which model string to use
    model = model_name or _selected_model or settings.get("ollamaModelName", "llama3")

    if provider == "openai":
        import openai
        api_key = settings.get("openAIApiKey")
        if not api_key:
            raise ValueError("OpenAI API key not configured in settings.")
        
        client = openai.OpenAI(api_key=api_key)
        # Use gpt-4o-mini as a default if the model passed is for ollama
        target_model = model if model and model not in ["llama3", "mistral"] else "gpt-4o-mini"
        
        response = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    elif provider == "gemini":
        import google.generativeai as genai
        api_key = settings.get("geminiApiKey")
        if not api_key:
            raise ValueError("Gemini API key not configured in settings.")
        
        genai.configure(api_key=api_key)
        target_model = model if model and model not in ["llama3", "mistral"] else "gemini-1.5-flash"
        generative_model = genai.GenerativeModel(target_model)
        
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
