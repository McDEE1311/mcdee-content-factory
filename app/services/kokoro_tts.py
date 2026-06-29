"""
Kokoro TTS service — natural AI voice generation using kokoro-onnx.
Falls back to espeak if models not available.
"""
import logging
import os
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Model paths — stored in project root
_REPO_ROOT = Path(__file__).parent.parent.parent
KOKORO_MODEL = str(_REPO_ROOT / "kokoro-v1.0.onnx")
VOICES_FILE = str(_REPO_ROOT / "voices-v1.0.bin")

# Documentary voices — alternating between videos
DOCUMENTARY_VOICES = ["bm_george", "am_onyx"]
VOICES = DOCUMENTARY_VOICES

def get_next_voice() -> str:
    """Alternate between bm_george and am_onyx across videos."""
    import os
    counter_file = "/tmp/voice_counter.txt"
    try:
        count = int(open(counter_file).read().strip()) if os.path.exists(counter_file) else 0
    except Exception:
        count = 0
    voice = DOCUMENTARY_VOICES[count % len(DOCUMENTARY_VOICES)]
    with open(counter_file, "w") as f:
        f.write(str(count + 1))
    return voice


def is_available() -> bool:
    """Check if Kokoro models are downloaded."""
    return os.path.exists(KOKORO_MODEL) and os.path.exists(VOICES_FILE)


def generate_wav(text: str, output_path: str, voice: str = "af_heart", speed: float = 1.0) -> bool:
    """
    Generate WAV file from text using Kokoro TTS.
    Returns True on success.
    """
    if not is_available():
        logger.warning(f"[kokoro] Model files not found. Run: wget {KOKORO_MODEL}")
        return _fallback_tts(text, output_path)

    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        kokoro = Kokoro(KOKORO_MODEL, VOICES_FILE)
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us")

        sf.write(output_path, samples, sample_rate)
        size_kb = os.path.getsize(output_path) // 1024
        logger.info(f"[kokoro] Generated {size_kb}KB WAV: {output_path}")
        return True

    except ImportError:
        logger.warning("[kokoro] kokoro_onnx or soundfile not installed")
        return _fallback_tts(text, output_path)
    except Exception as e:
        logger.error(f"[kokoro] Generation failed: {e}")
        return _fallback_tts(text, output_path)


def _fallback_tts(text: str, output_path: str) -> bool:
    """Fallback to espeak-ng if Kokoro unavailable."""
    import subprocess
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        cmd = ["espeak-ng", "-w", output_path, "--speed=150", "-v", "en-us", text[:2000]]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"[tts] espeak-ng fallback: {output_path}")
            return True
    except Exception as e:
        logger.warning(f"[tts] espeak-ng failed: {e}")
    return False


def generate_wav_chunked(text: str, output_path: str, voice: str = None) -> bool:
    if voice is None:
        try:
            voice = get_next_voice()
        except Exception:
            voice = "bm_george"
    """
    Generate WAV for long scripts by chunking into paragraphs.
    Concatenates chunks into a single WAV file.
    """
    if not is_available():
        return generate_wav(text, output_path, voice)

    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        # Split into chunks of ~500 chars at sentence boundaries
        chunks = _split_text(text, max_chars=500)
        logger.info(f"[kokoro] Processing {len(chunks)} chunks")

        kokoro = Kokoro(KOKORO_MODEL, VOICES_FILE)
        all_samples = []
        sample_rate = 24000

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            samples, sr = kokoro.create(chunk.strip(), voice=voice, speed=1.0, lang="en-us")
            sample_rate = sr
            all_samples.append(samples)
            # Add small pause between chunks
            pause = np.zeros(int(sr * 0.3))
            all_samples.append(pause)

        if all_samples:
            combined = np.concatenate(all_samples)
            sf.write(output_path, combined, sample_rate)
            duration = len(combined) / sample_rate
            logger.info(f"[kokoro] Generated {duration:.1f}s audio: {output_path}")
            return True

    except Exception as e:
        logger.error(f"[kokoro] Chunked generation failed: {e}")
        return generate_wav(text, output_path, voice)

    return False


def _split_text(text: str, max_chars: int = 500) -> list:
    """Split text into chunks at sentence boundaries."""
    import re
    # Split on sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_chars:
            current += " " + sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence
    if current:
        chunks.append(current.strip())
    return chunks
