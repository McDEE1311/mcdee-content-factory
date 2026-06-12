"""
Video render service using moviepy + ffmpeg.
Creates MP4 videos from script/thumbnail/voiceover assets.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def is_ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_moviepy_available() -> bool:
    try:
        import moviepy.editor
        return True
    except ImportError:
        return False


def render_simple_video(
    thumbnail_path: str,
    audio_path: Optional[str],
    script_text: str,
    title: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
) -> bool:
    """
    Render a simple video:
    - Static or scrolling background image
    - Voiceover audio
    - Burned-in subtitles
    Returns True if successful.
    """
    if not is_ffmpeg_available():
        logger.warning("[render] ffmpeg not available. Cannot render video.")
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Determine duration from audio, or default to 5 minutes
    duration = _get_audio_duration(audio_path) if audio_path else 300.0

    try:
        if is_moviepy_available():
            return _render_moviepy(
                thumbnail_path, audio_path, script_text, title, output_path, duration, width, height
            )
        else:
            return _render_ffmpeg(
                thumbnail_path, audio_path, output_path, duration, width, height
            )
    except Exception as e:
        logger.error(f"[render] Video render failed: {e}")
        return False


def _render_moviepy(
    thumbnail_path: str,
    audio_path: Optional[str],
    script_text: str,
    title: str,
    output_path: str,
    duration: float,
    width: int,
    height: int,
) -> bool:
    """Render using moviepy."""
    try:
        from moviepy.editor import (
            ImageClip, AudioFileClip, CompositeVideoClip,
            TextClip, concatenate_videoclips, ColorClip
        )

        clips = []

        # Background
        if thumbnail_path and os.path.exists(thumbnail_path):
            bg = ImageClip(thumbnail_path).set_duration(duration).resize((width, height))
        else:
            bg = ColorClip(size=(width, height), color=(10, 10, 20)).set_duration(duration)
        clips.append(bg)

        # Title text overlay
        try:
            title_clip = (
                TextClip(title[:80], fontsize=60, color="white", font="DejaVu-Sans-Bold",
                         method="caption", size=(width - 200, None))
                .set_position(("center", 50))
                .set_duration(min(duration, 8.0))
                .fadein(0.5)
                .fadeout(0.5)
            )
            clips.append(title_clip)
        except Exception:
            pass  # Skip text if font unavailable

        video = CompositeVideoClip(clips)

        # Add audio if available
        if audio_path and os.path.exists(audio_path):
            try:
                audio = AudioFileClip(audio_path)
                video = video.set_audio(audio)
            except Exception as e:
                logger.warning(f"[render] Could not add audio: {e}")

        video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=output_path + ".temp_audio.m4a",
            remove_temp=True,
            logger=None,
            threads=4,
        )
        logger.info(f"[render] Video rendered: {output_path}")
        return True

    except Exception as e:
        logger.error(f"[render] moviepy failed: {e}")
        return False


def _render_ffmpeg(
    image_path: str,
    audio_path: Optional[str],
    output_path: str,
    duration: float,
    width: int,
    height: int,
) -> bool:
    """Render using pure ffmpeg (no moviepy)."""
    try:
        if image_path and os.path.exists(image_path):
            input_args = ["-loop", "1", "-i", image_path]
        else:
            # Black background
            input_args = ["-f", "lavfi", "-i", f"color=c=black:size={width}x{height}:rate=24"]

        if audio_path and os.path.exists(audio_path):
            cmd = [
                "ffmpeg", "-y",
                *input_args,
                "-i", audio_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={width}:{height}",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                *input_args,
                "-t", str(duration),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={width}:{height}",
                output_path,
            ]

        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"[render] ffmpeg video: {output_path}")
            return True
        else:
            logger.error(f"[render] ffmpeg error: {result.stderr.decode()[:500]}")
            return False
    except Exception as e:
        logger.error(f"[render] ffmpeg failed: {e}")
        return False


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 300.0
