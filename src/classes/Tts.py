import os
import re


class TTS:
    def __init__(self) -> None:
        from config import (
            get_tts_provider,
            get_tts_voice,
            get_tts_openai_model,
            get_tts_openai_voice,
            get_tts_openai_speed,
            get_tts_openai_instructions,
            get_openai_api_key,
        )

        self.provider = str(get_tts_provider() or "auto").strip().lower()
        self.voice = str(get_tts_voice() or "Jasper").strip()
        self.openai_model = str(get_tts_openai_model() or "gpt-4o-mini-tts").strip()
        self.openai_voice = str(get_tts_openai_voice() or "verse").strip()
        self.openai_speed = float(get_tts_openai_speed() or 1.0)
        self.openai_instructions = str(get_tts_openai_instructions() or "").strip()
        self.openai_api_key = str(get_openai_api_key() or "").strip()

    def _detect_language_mix(self, text: str) -> str:
        sample = str(text or "").lower()
        filipino_markers = [
            "mga", "naman", "kasi", "po", "opo", "hindi", "paano", "ikaw",
            "ako", "tayo", "sila", "ng", "sa", "para", "at", "pero", "kayo",
            "salamat", "kamusta", "gusto", "dito", "doon", "kapag", "lang",
        ]
        english_markers = [
            "the", "and", "you", "your", "this", "that", "with", "for",
            "business", "marketing", "video", "content", "growth", "audience",
        ]

        fil_hits = sum(1 for token in filipino_markers if re.search(rf"\b{re.escape(token)}\b", sample))
        en_hits = sum(1 for token in english_markers if re.search(rf"\b{re.escape(token)}\b", sample))

        if fil_hits >= 2 and en_hits >= 2:
            return "mixed"
        if fil_hits >= 2:
            return "filipino"
        return "english"

    def _resolve_edge_voice(self, text: str) -> str:
        configured = str(self.voice or "").strip()
        lowered = configured.lower()

        # Keep explicit Edge voice IDs unchanged.
        if configured and "-" in configured and "neural" in lowered:
            return configured

        language_mix = self._detect_language_mix(text)
        if language_mix in {"mixed", "filipino"}:
            return "fil-PH-BlessicaNeural"
        return "en-US-JennyNeural"

    def _resolve_openai_api_key(self) -> str:
        if self.openai_api_key:
            return self.openai_api_key

        env_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if env_key:
            return env_key

        try:
            from llm_provider import get_settings

            settings = get_settings() or {}
            key = str(settings.get("openAIApiKey") or settings.get("OpenAIApiKey") or "").strip()
            if key:
                return key
        except Exception:
            pass

        return ""

    def _synthesize_with_openai(self, text: str, file_path: str) -> bool:
        api_key = self._resolve_openai_api_key()
        if not api_key:
            return False

        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            response = client.audio.speech.create(
                model=self.openai_model,
                voice=self.openai_voice,
                input=text,
                instructions=self.openai_instructions,
                response_format="wav",
                speed=self.openai_speed,
            )
            response.stream_to_file(file_path)
            return True
        except Exception as exc:
            print(f"OpenAI TTS failed, falling back to Edge voice: {exc}")
            return False

    def _synthesize_with_edge(self, text: str, file_path: str) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Install dependency 'edge-tts' or configure OpenAI TTS."
            ) from exc

        voice = self._resolve_edge_voice(text)
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
        )
        communicate.save_sync(file_path)

    def synthesize(self, text: str, file_path: str) -> None:
        """
        Synthesizes text using the configured provider with human-like defaults.

        Provider selection:
          - 'openai': OpenAI TTS only (fails if unavailable)
          - 'edge': Edge neural TTS only
          - 'auto': OpenAI first, Edge fallback
        """
        cleaned_text = " ".join(str(text or "").split())
        if not cleaned_text:
            raise ValueError("TTS input text is empty.")

        provider = self.provider or "auto"
        if provider in {"openai", "auto"}:
            generated = self._synthesize_with_openai(cleaned_text, file_path)
            if generated:
                return
            if provider == "openai":
                raise RuntimeError("OpenAI TTS provider selected but synthesis failed.")

        self._synthesize_with_edge(cleaned_text, file_path)
