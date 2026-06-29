"""
Scene Timing Service
Uses Whisper to get word-level timestamps from narration audio.
Finds natural pause points to use as scene cut points.
This ensures scenes change at speech boundaries, not mid-sentence.
"""
import logging
import json
import os
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

MIN_PAUSE_SECONDS = 0.4   # Minimum silence gap to trigger scene change
MIN_SCENE_SECONDS = 3.0   # Minimum scene duration
MAX_SCENE_SECONDS = 7.0   # Maximum scene duration before forced cut


def get_word_timestamps(audio_path: str, model_size: str = "base") -> List[Dict]:
    """
    Run Whisper on audio file and return word-level timestamps.
    Returns list of {word, start, end} dicts.
    """
    import whisper
    logger.info(f"[timing] Loading Whisper {model_size} model...")
    model = whisper.load_model(model_size)

    logger.info(f"[timing] Transcribing: {audio_path}")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        verbose=False,
    )

    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })

    logger.info(f"[timing] Got {len(words)} word timestamps")
    return words


def find_scene_cut_points(words: List[Dict], audio_duration: float) -> List[float]:
    """
    Find natural scene cut points from word timestamps.
    Cuts happen at:
    1. Pauses between words longer than MIN_PAUSE_SECONDS
    2. Forced cuts if a scene would exceed MAX_SCENE_SECONDS
    Always respect MIN_SCENE_SECONDS between cuts.

    Returns list of timestamps (in seconds) where scenes should change.
    """
    if not words:
        # Fallback: cut every 5 seconds
        return list(range(0, int(audio_duration), 5))

    cut_points = [0.0]  # Always start at 0
    last_cut = 0.0

    for i in range(1, len(words)):
        current_time = words[i]["start"]
        prev_end = words[i-1]["end"]
        gap = current_time - prev_end
        time_since_cut = current_time - last_cut

        # Forced cut if scene too long
        if time_since_cut >= MAX_SCENE_SECONDS:
            cut_points.append(prev_end)
            last_cut = prev_end
            continue

        # Natural pause cut
        if gap >= MIN_PAUSE_SECONDS and time_since_cut >= MIN_SCENE_SECONDS:
            cut_point = prev_end + (gap * 0.3)  # Cut 30% into the pause
            cut_points.append(cut_point)
            last_cut = cut_point

    # Add final cut at end
    if audio_duration - last_cut > MIN_SCENE_SECONDS:
        cut_points.append(audio_duration)

    logger.info(f"[timing] Found {len(cut_points)} scene cut points")
    return cut_points


def get_scene_durations(cut_points: List[float], audio_duration: float) -> List[Dict]:
    """
    Convert cut points into list of scenes with start/end/duration.
    """
    scenes = []
    for i in range(len(cut_points) - 1):
        start = cut_points[i]
        end = cut_points[i + 1]
        duration = end - start
        scenes.append({
            "scene_index": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
        })
    logger.info(f"[timing] {len(scenes)} scenes, avg {audio_duration/len(scenes):.1f}s each")
    return scenes


def analyze_audio(audio_path: str, output_json: str = None) -> List[Dict]:
    """
    Full pipeline: audio → Whisper → cut points → scene list.
    Optionally saves to JSON.
    """
    import subprocess

    # Get audio duration
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    duration = float(r.stdout.strip())
    logger.info(f"[timing] Audio duration: {duration:.1f}s")

    words = get_word_timestamps(audio_path)
    cut_points = find_scene_cut_points(words, duration)
    scenes = get_scene_durations(cut_points, duration)

    if output_json:
        os.makedirs(os.path.dirname(output_json) if os.path.dirname(output_json) else ".", exist_ok=True)
        with open(output_json, "w") as f:
            json.dump({
                "audio_path": audio_path,
                "duration": duration,
                "scene_count": len(scenes),
                "cut_points": cut_points,
                "scenes": scenes,
            }, f, indent=2)
        logger.info(f"[timing] Saved timing to {output_json}")

    return scenes
