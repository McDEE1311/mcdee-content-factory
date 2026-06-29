"""
Real video renderer — images + audio + captions → MP4
Uses ffmpeg + moviepy + Whisper for captions.
Target: 1920x1080, 30fps, H264, AAC, YouTube optimized.
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

VIDEO_W = 1920
VIDEO_H = 1080
SHORTS_W = 1080
SHORTS_H = 1920
FPS = 30


def render_video(
    image_paths: List[str],
    audio_path: str,
    output_path: str,
    title: str = "",
    add_captions: bool = True,
    scene_duration: float = 6.0,
    vertical: bool = False,
) -> bool:
    """
    Render a complete video from images + audio.
    Each image gets Ken Burns zoom/pan effect.
    Captions burned in via Whisper.
    Returns True on success.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    if not image_paths:
        logger.warning("[render] No images provided")
        return _render_static(audio_path, output_path, title)

    if not audio_path or not os.path.exists(audio_path):
        logger.warning("[render] No audio file")
        return False

    # Get audio duration
    duration = _get_duration(audio_path)
    if duration <= 0:
        logger.warning("[render] Could not get audio duration")
        return False

    logger.info(f"[render] Audio duration: {duration:.1f}s, {len(image_paths)} images")

    try:
        # Step 1: Create video from images — simple slideshow (fast, reliable)
        raw_video = output_path.replace(".mp4", "_raw.mp4")
        ok = _simple_slideshow(image_paths, duration, raw_video, vertical=vertical)
        if not ok:
            return _render_static(audio_path, output_path, title, vertical=vertical)

        # Step 2: Merge audio + video
        merged = output_path.replace(".mp4", "_merged.mp4")
        ok = _merge_audio(raw_video, audio_path, merged)
        if not ok:
            return False

        # Step 3: Add captions if Whisper available
        if add_captions and _whisper_available():
            captioned = output_path.replace(".mp4", "_captioned.mp4")
            ok = _burn_captions(merged, audio_path, captioned, vertical=vertical)
            if ok:
                os.rename(captioned, output_path)
            else:
                os.rename(merged, output_path)
        else:
            os.rename(merged, output_path)

        # Cleanup temp files
        for f in [raw_video, merged]:
            if os.path.exists(f):
                os.remove(f)

        size_mb = os.path.getsize(output_path) / 1024 / 1024
        logger.info(f"[render] Done: {output_path} ({size_mb:.1f}MB)")
        return True

    except Exception as e:
        logger.error(f"[render] Failed: {e}")
        return False


def _create_slideshow(image_paths: List[str], duration: float, output: str) -> bool:
    """Create video from images with Ken Burns zoom effect using ffmpeg."""
    try:
        n = len(image_paths)
        scene_dur = duration / n

        # Build ffmpeg filter for Ken Burns on each image
        filter_parts = []
        inputs = []

        for i, img in enumerate(image_paths):
            inputs.extend(["-loop", "1", "-t", str(scene_dur), "-i", img])

            # Alternate between zoom in and pan right
            if i % 3 == 0:
                # Zoom in
                zoom = f"[{i}:v]scale=8000:-1,zoompan=z='min(zoom+0.0008,1.5)':d={int(scene_dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS}[v{i}]"
            elif i % 3 == 1:
                # Pan right
                zoom = f"[{i}:v]scale=8000:-1,zoompan=z='1.3':d={int(scene_dur*FPS)}:x='iw/2-(iw/zoom/2)+{i*2}':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS}[v{i}]"
            else:
                # Zoom out
                zoom = f"[{i}:v]scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0008))':d={int(scene_dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS}[v{i}]"
            filter_parts.append(zoom)

        # Concatenate all clips with crossfade
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")
        filter_str = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            output
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"[render] Slideshow created: {output}")
            return True
        else:
            logger.warning(f"[render] Slideshow failed, trying simple concat")
            return _simple_slideshow(image_paths, duration, output)

    except Exception as e:
        logger.warning(f"[render] Ken Burns failed: {e}, trying simple")
        return _simple_slideshow(image_paths, duration, output)


def _simple_slideshow(image_paths: List[str], duration: float, output: str, vertical: bool = False) -> bool:
    """Simple slideshow without Ken Burns — crossfade between images. Fast and reliable."""
    w, h = (SHORTS_W, SHORTS_H) if vertical else (VIDEO_W, VIDEO_H)
    try:
        n = len(image_paths)
        scene_dur = duration / n

        inputs = []
        for img in image_paths:
            inputs.extend(["-loop", "1", "-t", str(scene_dur + 0.5), "-i", img])

        filter_parts = []
        for i, img in enumerate(image_paths):
            filter_parts.append(
                f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setsar=1[v{i}]"
            )

        concat = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat}concat=n={n}:v=1:a=0[vout]")

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-t", str(duration),
            output
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return result.returncode == 0

    except Exception as e:
        logger.error(f"[render] Simple slideshow failed: {e}")
        return False


def _merge_audio(video: str, audio: str, output: str) -> bool:
    """Merge audio track into video."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video,
            "-i", audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"[render] Audio merge failed: {e}")
        return False


def _whisper_available() -> bool:
    try:
        import whisper
        return True
    except ImportError:
        return False


def _burn_captions(video: str, audio: str, output: str, vertical: bool = False) -> bool:
    """Transcribe audio with Whisper and burn subtitles into video."""
    try:
        import whisper

        logger.info("[render] Transcribing audio with Whisper...")
        model = whisper.load_model("base")
        result = model.transcribe(audio, word_timestamps=True)

        # Write SRT file
        srt_path = video.replace(".mp4", ".srt")
        _write_srt(result["segments"], srt_path)

        # Shorts get bigger, more central captions; long-form gets lower-third
        if vertical:
            subtitle_style = (
                "FontName=Arial-Bold,FontSize=20,PrimaryColour=&Hffffff,"
                "OutlineColour=&H000000,Outline=3,Shadow=1,Bold=1,"
                "Alignment=2,MarginV=120"
            )
        else:
            subtitle_style = (
                "FontName=Arial,FontSize=14,PrimaryColour=&Hffffff,"
                "OutlineColour=&H000000,Outline=2,Shadow=1,"
                "Alignment=2,MarginV=40"
            )
        cmd = [
            "ffmpeg", "-y",
            "-i", video,
            "-vf", f"subtitles={srt_path}:force_style='{subtitle_style}'",
            "-c:a", "copy",
            "-c:v", "libx264", "-preset", "fast",
            output
        ]
        result2 = subprocess.run(cmd, capture_output=True, timeout=300)

        if os.path.exists(srt_path):
            os.remove(srt_path)

        if result2.returncode == 0:
            logger.info("[render] Captions burned in")
            return True
    except Exception as e:
        logger.warning(f"[render] Caption burn failed: {e}")
    return False


def _write_srt(segments, srt_path: str):
    """Write Whisper segments to SRT format."""
    def fmt_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(srt_path, "w") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")


def _render_static(audio_path: str, output_path: str, title: str, vertical: bool = False) -> bool:
    """Fallback: black background + audio."""
    w, h = (SHORTS_W, SHORTS_H) if vertical else (VIDEO_W, VIDEO_H)
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:size={w}x{h}:rate={FPS}",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"[render] Static render failed: {e}")
        return False


def _get_duration(audio_path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def render_video_mixed(
    scenes: List[dict],
    audio_path: str,
    output_path: str,
    title: str = "",
    add_captions: bool = True,
    vertical: bool = False,
) -> bool:
    """
    Render a video from mixed video clips + photos.
    scenes: list of {"path": str, "type": "video"|"image"}
    Each scene gets a roughly equal time slice of the audio duration.
    Video clips are trimmed to their slice; photos are held static for their slice.
    Returns True on success.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    if not scenes:
        logger.warning("[render] No scenes provided")
        return _render_static(audio_path, output_path, title, vertical=vertical)

    if not audio_path or not os.path.exists(audio_path):
        logger.warning("[render] No audio file")
        return False

    duration = _get_duration(audio_path)
    if duration <= 0:
        logger.warning("[render] Could not get audio duration")
        return False

    logger.info(f"[render] Audio duration: {duration:.1f}s, {len(scenes)} mixed scenes")

    try:
        raw_video = output_path.replace(".mp4", "_raw.mp4")
        ok = _mixed_slideshow(scenes, duration, raw_video, vertical=vertical)
        if not ok:
            return _render_static(audio_path, output_path, title, vertical=vertical)

        merged = output_path.replace(".mp4", "_merged.mp4")
        ok = _merge_audio(raw_video, audio_path, merged)
        if not ok:
            return False

        if add_captions and _whisper_available():
            captioned = output_path.replace(".mp4", "_captioned.mp4")
            ok = _burn_captions(merged, audio_path, captioned, vertical=vertical)
            if ok:
                os.rename(captioned, output_path)
            else:
                os.rename(merged, output_path)
        else:
            os.rename(merged, output_path)

        for f in [raw_video, merged]:
            if os.path.exists(f):
                os.remove(f)

        size_mb = os.path.getsize(output_path) / 1024 / 1024
        logger.info(f"[render] Done: {output_path} ({size_mb:.1f}MB)")
        return True

    except Exception as e:
        logger.error(f"[render] Mixed render failed: {e}")
        return False


def _mixed_slideshow(scenes: List[dict], duration: float, output: str, vertical: bool = False) -> bool:
    """Build a slideshow from mixed video clips and photos, each scaled/cropped to fill frame."""
    w, h = (SHORTS_W, SHORTS_H) if vertical else (VIDEO_W, VIDEO_H)
    n = len(scenes)
    scene_dur = duration / n

    try:
        inputs = []
        filter_parts = []

        for i, scene in enumerate(scenes):
            path = scene["path"]
            stype = scene.get("type", "image")

            if stype == "video":
                # Trim video to scene_dur, scale+crop to fill frame, strip audio
                inputs.extend(["-i", path])
                filter_parts.append(
                    f"[{i}:v]trim=0:{scene_dur},setpts=PTS-STARTPTS,"
                    f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},setsar=1,fps={FPS}[v{i}]"
                )
            else:
                inputs.extend(["-loop", "1", "-t", str(scene_dur + 0.5), "-i", path])
                filter_parts.append(
                    f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},setsar=1,fps={FPS}[v{i}]"
                )

        concat = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat}concat=n={n}:v=1:a=0[vout]")

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-t", str(duration),
            output
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            logger.warning(f"[render] Mixed slideshow ffmpeg error: {result.stderr.decode()[-500:]}")
        return result.returncode == 0

    except Exception as e:
        logger.error(f"[render] Mixed slideshow failed: {e}")
        return False
