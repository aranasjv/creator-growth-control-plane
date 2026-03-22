import os
import subprocess
import asyncio

class TTS:
    def __init__(self):
        from config import get_tts_voice
        self.voice = get_tts_voice()

    def synthesize(self, text: str, file_path: str) -> None:
        """
        Synthesizes text to speech natively using Microsoft Edge's cloud TTS engine.
        Outputs to the requested file_path so MoviePy can merge it with the video.
        """
        try:
            import edge_tts
        except ImportError:
            subprocess.run(["pip", "install", "edge-tts"], check=True)
            import edge_tts

        async def _run_tts():
            # Standardize the voice fallback in case legacy Kitten voices were requested
            v = self.voice
            if "Jasper" in v or "kitten" in v.lower() or "-" not in v:
                v = "en-US-GuyNeural"
                
            communicate = edge_tts.Communicate(text, v)
            await communicate.save(file_path)
            
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Ensure safe nested execution if the orchestrator is running its own async loop
            task = loop.create_task(_run_tts())
            loop.run_until_complete(task)
        else:
            asyncio.run(_run_tts())
