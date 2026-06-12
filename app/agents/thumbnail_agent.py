"""
Thumbnail Agent - generates YouTube thumbnails using Pillow.
"""
import logging, os, re
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Topic, Script, Asset
from app.services.image_service import create_thumbnail

logger = logging.getLogger(__name__)

def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:60] or "topic"

def generate_thumbnail(topic, script, output_dir, db):
    output_path = os.path.join(output_dir, "thumbnail.png")
    if os.path.exists(output_path):
        return output_path
    os.makedirs(output_dir, exist_ok=True)
    title_text = (script.title if script else topic.title) or topic.title
    theme_index = (topic.id or 0) % 5
    success = create_thumbnail(title=title_text, output_path=output_path, theme_index=theme_index)
    if success:
        db.add(Asset(topic_id=topic.id, asset_type="thumbnail", path=output_path,
                     metadata_json={"width": 1280, "height": 720, "theme": theme_index}))
        db.flush()
        logger.info(f"[thumbnail] Created: {output_path}")
        return output_path
    logger.warning(f"[thumbnail] Failed for topic {topic.id}")
    return None

def run_thumbnail_phase(db, topics, base_output_dir="outputs", run_date=None):
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
    results = {}
    for topic in topics:
        slug = _slugify(topic.title[:50])
        output_dir = os.path.join(base_output_dir, run_date, slug)
        script = db.query(Script).filter(Script.topic_id == topic.id).first()
        results[topic.id] = generate_thumbnail(topic, script, output_dir, db)
    return results
