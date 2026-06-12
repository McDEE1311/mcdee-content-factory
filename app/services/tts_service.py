"""
TTS Service - generates voiceover WAV files.
Supports Piper (local) with graceful fallback.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.settings import settings

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self):
        self.engine = settings.TTS_ENGINE
        self.voice_model = settings.VOICE_MODEL

    def is_piper_available(self) -> bool:
        """Check if piper TTS binary is available."""
        try:
            result = subprocess.run(["piper", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def generate_wav(self, text: str, output_path: str) -> bool:
        """
        Generate a WAV file from text.
        Returns True on success, False on failure.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if self.engine == "piper" and self.is_piper_available():
            return self._piper_tts(text, output_path)

        # Fallback: try espeak
        if self._espeak_available():
            return self._espeak_tts(text, output_path)

        # Final fallback: save script text and note placeholder
        logger.warning(f"[tts] No TTS engine available. Saving placeholder at {output_path}")
        placeholder_path = output_path.replace(".wav", "_tts_placeholder.txt")
        with open(placeholder_path, "w") as f:
            f.write(text)
        return False

    def _piper_tts(self, text: str, output_path: str) -> bool:
        """Generate voice using Piper TTS."""
        try:
            # Find model file
            model_path = self._find_piper_model()
            if not model_path:
                logger.warning(f"[tts] Piper model not found: {self.voice_model}")
                return False

            cmd = [
                "piper",
                "--model", model_path,
                "--output_file", output_path,
            ]
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0:
                logger.info(f"[tts] Piper generated: {output_path}")
                return True
            else:
                logger.warning(f"[tts] Piper error: {result.stderr.decode()}")
                return False
        except Exception as e:
            logger.warning(f"[tts] Piper failed: {e}")
            return False

    def _find_piper_model(self) -> Optional[str]:
        """Look for piper model file in common locations."""
        search_dirs = [
            os.path.expanduser("~/.local/share/piper"),
            os.path.expanduser("~/piper-models"),
            "/usr/share/piper",
            "/opt/piper/models",
        ]
        model_name = self.voice_model
        for d in search_dirs:
            candidate = os.path.join(d, f"{model_name}.onnx")
            if os.path.exists(candidate):
                return candidate
        return None

    def _espeak_available(self) -> bool:
        try:
            subprocess.run(["espeak", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _espeak_tts(self, text: str, output_path: str) -> bool:
        """Fallback to espeak."""
        try:
            cmd = ["espeak", "-w", output_path, text[:2000]]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                logger.info(f"[tts] espeak generated: {output_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"[tts] espeak failed: {e}")
            return False


tts_service = TTSService()
