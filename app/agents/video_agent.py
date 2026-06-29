"""
Video Agent - builds upload packages from scripts and assets.
Uses Pexels scene images + Kokoro voiceover + ffmpeg renderer.
"""
import json
import logging
import os
import re
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Script, Asset, Video
from app.services.render_service import is_ffmpeg_available
from app.services.pexels_client import fetch_scene_images
from app.services.video_renderer import render_video
from app.settings import settings

logger = logging.getLogger(__name__)


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:60] or "topic"


def _get_audio_duration(audio_path: str) -> float:
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
            capture_output=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _target_image_count(duration: float) -> int:
    min_images = int(getattr(settings, "VIDEO_MIN_IMAGES", 10))
    max_images = int(getattr(settings, "VIDEO_MAX_IMAGES", 30))

    if duration <= 0:
        target = min_images
    else:
        # roughly one image every 6-8 seconds
        target = int(duration / 7) + 1

    return max(min_images, min(max_images, target))


def build_upload_package(topic, script, output_dir, db, render_video_enabled=True):
    os.makedirs(output_dir, exist_ok=True)

    assets = db.query(Asset).filter(Asset.topic_id == topic.id).all()
    asset_map = {a.asset_type: a.path for a in assets}

    thumbnail_path = asset_map.get("thumbnail")
    audio_path = asset_map.get("voiceover")

    metadata = {
        "topic_id": topic.id,
        "title": script.title or topic.title,
        "description": script.description or "",
        "tags": script.tags_json or [],
        "thumbnail_prompt": script.thumbnail_prompt or "",
        "niche": topic.niche,
        "score": topic.final_score,
        "word_count": script.word_count,
    }

    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    with open(os.path.join(output_dir, "x_post.txt"), "w") as f:
        f.write(script.x_post or f"New video: {script.title}\n[LINK]")

    with open(os.path.join(output_dir, "script.md"), "w") as f:
        f.write(f"# {script.title}\n\n")
        f.write(script.script_text or "")

    video_path = None
    video_status = "package_ready_no_render"
    duration = _get_audio_duration(audio_path) if audio_path else 0.0

    if render_video_enabled and is_ffmpeg_available() and audio_path and os.path.exists(audio_path):
        video_path_out = os.path.join(output_dir, "video.mp4")

        if not os.path.exists(video_path_out):
            scene_dir = os.path.join(output_dir, "scene_images")
            image_count = _target_image_count(duration)

            logger.info(f"[video] Fetching {image_count} Pexels images for: {topic.title[:70]}")
            image_paths = fetch_scene_images(
                script_text=script.script_text or "",
                title=script.title or topic.title,
                output_dir=scene_dir,
                max_images=image_count,
            )

            if not image_paths and thumbnail_path:
                image_paths = [thumbnail_path]

            success = render_video(
                image_paths=image_paths,
                audio_path=audio_path,
                output_path=video_path_out,
                title=script.title or topic.title,
                add_captions=False,
            )

            if success:
                video_path = video_path_out
                video_status = "rendered"
            else:
                video_status = "render_failed"
        else:
            video_path = video_path_out
            video_status = "rendered"

    v = db.query(Video).filter(Video.topic_id == topic.id).first()
    if not v:
        v = Video(
            topic_id=topic.id,
            script_id=script.id,
            video_path=video_path or "",
            package_path=output_dir,
            duration_seconds=duration,
            status=video_status,
            run_date=datetime.now().strftime("%Y-%m-%d"),
        )
        db.add(v)
    else:
        v.package_path = output_dir
        v.status = video_status
        v.duration_seconds = duration
        if video_path:
            v.video_path = video_path

    db.flush()
    logger.info(f"[video] Package ready: {output_dir} (status={video_status}, duration={duration:.1f}s)")
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

        pkg = build_upload_package(topic, script, output_dir, db, render_video_enabled=render_video)
        if pkg:
            packages.append(pkg)
            topic.status = "packaged"

    db.flush()
    logger.info(f"[video] Done: {len(packages)} packages created.")
    return packages
