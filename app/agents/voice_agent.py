"""
Voice Agent - generates TTS voiceover using Kokoro (natural AI voice).
Falls back to espeak-ng if Kokoro models not downloaded.
"""
import logging
import os
import re
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import Topic, Script, Asset
from app.services.kokoro_tts import generate_wav_chunked, is_available as kokoro_available

logger = logging.getLogger(__name__)


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text[:60] or "topic"


def clean_script_for_tts(script_text: str) -> str:
    """Remove section headers and markdown before TTS."""
    text = re.sub(r'\[.*?\]', '', script_text)
    text = re.sub(r'#+\s+', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_voiceover(topic: Topic, script: Script, output_dir: str, db: Session) -> tuple[Optional[str], bool]:
    """Generate voiceover WAV. Returns (path_or_None, was_real_audio)."""
    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.join(output_dir, "voiceover.wav")

    if os.path.exists(wav_path):
        logger.info(f"[voice] Already exists: {wav_path}")
        return wav_path, True

    script_text = script.script_text or ""
    if not script_text:
        return None, False

    # Save raw script text
    with open(os.path.join(output_dir, "script.txt"), "w") as f:
        f.write(script_text)

    # Clean for TTS
    clean_text = clean_script_for_tts(script_text)

    if kokoro_available():
        logger.info(f"[voice] Kokoro TTS: {topic.title[:60]}")
        success = generate_wav_chunked(clean_text, wav_path, voice="af_heart")
    else:
        logger.warning("[voice] Kokoro models not found — using espeak fallback")
        from app.services.kokoro_tts import _fallback_tts
        success = _fallback_tts(clean_text, wav_path)

    if success and os.path.exists(wav_path):
        size_kb = os.path.getsize(wav_path) // 1024
        asset = Asset(
            topic_id=topic.id,
            asset_type="voiceover",
            path=wav_path,
            metadata_json={"engine": "kokoro" if kokoro_available() else "espeak", "size_kb": size_kb},
        )
        db.add(asset)
        db.flush()
        logger.info(f"[voice] Generated {size_kb}KB: {wav_path}")
        return wav_path, True

    logger.warning(f"[voice] TTS failed for topic {topic.id}")
    return None, False


def run_voice_phase(db, topics, base_output_dir="outputs", run_date=None):
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
    results = {}
    for topic in topics:
        script = db.query(Script).filter(Script.topic_id == topic.id).first()
        if not script:
            continue
        slug = _slugify(topic.title[:50])
        output_dir = os.path.join(base_output_dir, run_date, slug)
        path, real = generate_voiceover(topic, script, output_dir, db)
        results[topic.id] = {"path": path, "real_audio": real}
    return results
