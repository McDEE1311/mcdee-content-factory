"""
Video Agent - builds upload packages from scripts and assets.
"""
import json, logging, os, re
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Topic, Script, Asset, Video
from app.services.render_service import render_simple_video, is_ffmpeg_available

logger = logging.getLogger(__name__)

def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:60] or "topic"

def build_upload_package(topic, script, output_dir, db, render_video=True):
    os.makedirs(output_dir, exist_ok=True)
    assets = db.query(Asset).filter(Asset.topic_id == topic.id).all()
    asset_map = {a.asset_type: a.path for a in assets}
    thumbnail_path = asset_map.get("thumbnail")
    audio_path = asset_map.get("voiceover")
    metadata = {"topic_id": topic.id, "title": script.title or topic.title,
                 "description": script.description or "", "tags": script.tags_json or [],
                 "thumbnail_prompt": script.thumbnail_prompt or "",
                 "niche": topic.niche, "score": topic.final_score, "word_count": script.word_count}
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(output_dir, "x_post.txt"), "w") as f:
        f.write(script.x_post or f"New video: {script.title}\n[LINK]")
    with open(os.path.join(output_dir, "script.md"), "w") as f:
        f.write(f"# {script.title}\n\n")
        f.write(script.script_text or "")
    video_path = None
    video_status = "package_ready_no_render"
    if render_video and is_ffmpeg_available():
        video_path_out = os.path.join(output_dir, "video.mp4")
        if not os.path.exists(video_path_out):
            success = render_simple_video(thumbnail_path=thumbnail_path or "",
                audio_path=audio_path, script_text=script.script_text or "",
                title=script.title or topic.title, output_path=video_path_out)
            if success:
                video_path = video_path_out
                video_status = "rendered"
        else:
            video_path = video_path_out
            video_status = "rendered"
    v = db.query(Video).filter(Video.topic_id == topic.id).first()
    if not v:
        v = Video(topic_id=topic.id, script_id=script.id, video_path=video_path or "",
                  package_path=output_dir, status=video_status,
                  run_date=datetime.now().strftime("%Y-%m-%d"))
        db.add(v)
    else:
        v.package_path = output_dir
        v.status = video_status
        if video_path:
            v.video_path = video_path
    db.flush()
    logger.info(f"[video] Package ready: {output_dir} (status={video_status})")
    return output_dir

def run_video_phase(db, topics, base_output_dir="outputs", run_date=None, render_video=True):
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
    packages = []
    for topic in topics:
        script = db.query(Script).filter(Script.topic_id == topic.id).first()
        if not script:
            continue
        slug = _slugify(topic.title[:50])
        output_dir = os.path.join(base_output_dir, "upload_packages", run_date, slug)
        pkg = build_upload_package(topic, script, output_dir, db, render_video=render_video)
        if pkg:
            packages.append(pkg)
            topic.status = "packaged"
    db.flush()
    logger.info(f"[video] Done: {len(packages)} packages created.")
    return packages
