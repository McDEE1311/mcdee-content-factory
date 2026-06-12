"""
Voice Agent - generates TTS voiceover for scripts.
"""
import logging, os, re
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Topic, Script, Asset
from app.services.tts_service import tts_service

logger = logging.getLogger(__name__)

def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:60] or "topic"

def generate_voiceover(topic, script, output_dir, db):
    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.join(output_dir, "voiceover.wav")
    if os.path.exists(wav_path):
        return wav_path, True
    script_text = script.script_text or ""
    if not script_text:
        return None, False
    with open(os.path.join(output_dir, "script.txt"), "w", encoding="utf-8") as f:
        f.write(script_text)
    success = tts_service.generate_wav(script_text, wav_path)
    if success and os.path.exists(wav_path):
        db.add(Asset(topic_id=topic.id, asset_type="voiceover", path=wav_path,
                     metadata_json={"engine": tts_service.engine}))
        db.flush()
        logger.info(f"[voice] Voiceover created: {wav_path}")
        return wav_path, True
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
