"""
Shorts Generator V2
Produces 3-5 vertical YouTube Shorts from a long-form documentary.
Each Short is a standalone hook that drives viewers to the full video.

Short types:
1. SHOCK    — shocking number or fact
2. VILLAIN  — introduce the antagonist
3. COLLAPSE — the dramatic falling apart
4. REVEAL   — the hidden truth uncovered
5. CLIFFHANGER — what happened next
"""
import json
import logging
import os
import re
import subprocess
from typing import List, Dict

logger = logging.getLogger(__name__)

CTA_OPTIONS = [
    "FULL STORY ON THE CHANNEL",
    "WATCH THE FULL DOCUMENTARY",
    "SEE THE COMPLETE STORY",
]


def extract_short_moments(script_text: str, title: str, topic: str) -> List[Dict]:
    """Extract 3-5 viral Short moments from a long-form script."""
    from app.services.ollama_client import ollama_client

    # Clean script
    clean = re.sub(r'\[.*?\]', '', script_text)
    clean = re.sub(r'#{1,4}\s*', '', clean)
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()

    system = """You extract viral short-form moments from documentary scripts.
You think like a social media editor — find the moments that stop someone mid-scroll.
Output ONLY valid JSON. No markdown. No explanation."""

    prompt = f"""Documentary title: {title}
Topic: {topic}

Script excerpt (first 1500 words):
{clean[:1500]}

Extract exactly 3 Short-form moments from this script.
Each Short must work as a STANDALONE 30-55 second clip with no context needed.

Short types to find:
1. SHOCK — a shocking number, date, or fact that stops someone scrolling
2. VILLAIN — introduce the villain in the most compelling way
3. COLLAPSE — the dramatic moment everything fell apart

For each Short, write a self-contained 30-55 second narration script.
Start each with a hook. End each with a cliffhanger or open question.
The last line of every Short must be: "Full story on the channel."

Output this exact JSON:
[
  {{
    "type": "SHOCK",
    "title": "YouTube Shorts title under 50 chars",
    "script": "complete 30-55 second narration text",
    "hook": "opening 5 words"
  }},
  {{
    "type": "VILLAIN",
    "title": "YouTube Shorts title under 50 chars", 
    "script": "complete 30-55 second narration text",
    "hook": "opening 5 words"
  }},
  {{
    "type": "COLLAPSE",
    "title": "YouTube Shorts title under 50 chars",
    "script": "complete 30-55 second narration text",
    "hook": "opening 5 words"
  }}
]"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.8)
        if isinstance(result, list) and len(result) > 0:
            logger.info(f"[shorts] Extracted {len(result)} Short moments")
            return result[:5]
    except Exception as e:
        logger.warning(f"[shorts] Extraction failed: {e}")

    # Fallback moments
    return [
        {"type": "SHOCK", "title": f"{title[:45]} #shorts",
         "script": f"What you're about to hear is one of the most shocking financial stories ever told. Full story on the channel.",
         "hook": "What you're about to hear"},
        {"type": "VILLAIN", "title": f"The Man Behind It All #shorts",
         "script": f"He convinced everyone he was a genius. He wasn't. Full story on the channel.",
         "hook": "He convinced everyone"},
        {"type": "COLLAPSE", "title": f"When It All Fell Apart #shorts",
         "script": f"Nobody saw it coming. And by the time they did, it was already too late. Full story on the channel.",
         "hook": "Nobody saw it coming"},
    ]


def generate_short_audio(script_text: str, output_wav: str, voice: str = "bm_george") -> bool:
    """Generate TTS audio for a Short."""
    try:
        from app.services.kokoro_tts import generate_wav_chunked
        from app.services.text_normalizer import normalize_for_tts
        clean = normalize_for_tts(script_text)
        return generate_wav_chunked(clean, output_wav, voice=voice)
    except Exception as e:
        logger.error(f"[shorts] Audio generation failed: {e}")
        return False


def render_vertical_short(
    scene_images: List[str],
    audio_path: str,
    output_path: str,
    cta_text: str = "FULL STORY ON THE CHANNEL",
) -> bool:
    """
    Render a vertical 1080x1920 Short from scene images and audio.
    Uses center crop of horizontal images + Ken Burns effect.
    """
    if not scene_images or not os.path.exists(audio_path):
        logger.error("[shorts] Missing scenes or audio")
        return False

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    # Get audio duration
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    try:
        duration = float(r.stdout.strip())
    except Exception:
        duration = 45.0

    # Build clips directory
    clips_dir = output_path.replace(".mp4", "_clips")
    os.makedirs(clips_dir, exist_ok=True)

    scene_dur = duration / len(scene_images)
    clip_paths = []

    for i, img in enumerate(scene_images):
        clip_out = os.path.join(clips_dir, f"clip_{i:03d}.mp4")

        # Vertical crop: take center 9:16 portion of 16:9 image
        # 1024x576 source → crop to 324x576 center → scale to 1080x1920
        vf = (
            f"crop=324:576:350:0,"
            f"scale=1080:1920,"
            f"zoompan=z='min(zoom+0.0003,1.2)':d={int(scene_dur*25)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=25"
        )

        r2 = subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", str(scene_dur + 0.5),
            "-i", img, "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-t", str(scene_dur), clip_out
        ], capture_output=True, timeout=60)

        if r2.returncode == 0:
            clip_paths.append(clip_out)
        else:
            # Static fallback
            r3 = subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-t", str(scene_dur),
                "-i", img,
                "-vf", "crop=324:576:350:0,scale=1080:1920,setsar=1,fps=25",
                "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", clip_out
            ], capture_output=True, timeout=30)
            if r3.returncode == 0:
                clip_paths.append(clip_out)

    if not clip_paths:
        logger.error("[shorts] No clips generated")
        return False

    # Concat clips
    concat_file = os.path.join(clips_dir, "concat.txt")
    with open(concat_file, "w") as f:
        needed = int(duration / scene_dur) + 2
        for i in range(needed):
            f.write(f"file '{os.path.abspath(clip_paths[i % len(clip_paths)])}'\n")

    raw_video = output_path.replace(".mp4", "_raw.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file, "-c", "copy", "-t", str(duration), raw_video
    ], capture_output=True, timeout=120)

    if not os.path.exists(raw_video):
        logger.error("[shorts] Concat failed")
        return False

    # Merge audio
    r4 = subprocess.run([
        "ffmpeg", "-y",
        "-i", raw_video, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ], capture_output=True, timeout=60)

    if os.path.exists(raw_video):
        os.remove(raw_video)

    if os.path.exists(output_path):
        mb = os.path.getsize(output_path) / 1024 / 1024
        logger.info(f"[shorts] Rendered: {output_path} ({mb:.1f}MB)")
        return True

    logger.error("[shorts] Final render failed")
    return False


def generate_shorts_package(
    long_video_path: str,
    script_text: str,
    title: str,
    topic: str,
    output_dir: str,
    scene_images: List[str],
    voice: str = "bm_george",
) -> List[str]:
    """
    Generate 3 YouTube Shorts from a long-form documentary.
    Returns list of output Short video paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"[shorts] Generating 3 Shorts for: {title[:50]}")

    moments = extract_short_moments(script_text, title, topic)
    generated = []

    for i, moment in enumerate(moments[:3]):
        short_dir = os.path.join(output_dir, f"short_{i+1:02d}")
        os.makedirs(short_dir, exist_ok=True)

        short_type = moment.get("type", "SHOCK")
        short_title = moment.get("title", f"{title[:40]} #{i+1}")
        short_script = moment.get("script", "")
        cta = CTA_OPTIONS[i % len(CTA_OPTIONS)]

        logger.info(f"[shorts] Short {i+1}: {short_type} — {short_title[:40]}")

        # Generate audio
        wav_path = os.path.join(short_dir, "narration.wav")
        if not generate_short_audio(short_script, wav_path, voice):
            logger.warning(f"[shorts] Audio failed for Short {i+1}")
            continue

        # Select scenes — use different subset for each Short
        total_scenes = len(scene_images)
        start_idx = (i * total_scenes // 3) % total_scenes
        subset = scene_images[start_idx:start_idx + 8]
        if len(subset) < 3:
            subset = scene_images[:8]

        # Render vertical Short
        out_path = os.path.join(short_dir, "short.mp4")
        ok = render_vertical_short(subset, wav_path, out_path, cta)

        if ok:
            # Save metadata
            with open(os.path.join(short_dir, "metadata.txt"), "w") as f:
                f.write(f"Type: {short_type}\n")
                f.write(f"Title: {short_title}\n")
                f.write(f"Hook: {moment.get('hook', '')}\n")
                f.write(f"Script:\n{short_script}\n")
                f.write(f"CTA: {cta}\n")
            generated.append(out_path)
            logger.info(f"[shorts] Short {i+1} complete: {out_path}")
        else:
            logger.warning(f"[shorts] Short {i+1} render failed")

    logger.info(f"[shorts] Package complete: {len(generated)}/3 Shorts")
    return generated
