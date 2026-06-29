"""
Pexels Stock Video Client
Searches and downloads real footage matched to storyboard scenes.
This replaces SD image generation for scene visuals.
"""
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "CzdNW7RTpYlN0dm7Hyj8QFsfJWTalBM3rdznsaQPtQnwpTunaeEwUtQI")
HEADERS = {"Authorization": PEXELS_API_KEY}

# Scene type → Pexels search queries
# Ordered by relevance — first query is primary
SCENE_QUERY_MAP = {
    # Financial
    "trading": ["stock market trading floor", "Wall Street traders", "financial trading"],
    "office": ["executive office Manhattan", "businessman office window", "corporate office luxury"],
    "meeting": ["business meeting boardroom", "investors conference room", "corporate presentation"],
    "fraud": ["financial documents fraud", "money counting", "financial crime investigation"],
    "money": ["money cash bills", "financial wealth", "dollar bills"],
    "investor": ["investors business meeting", "wealth management", "financial advisor"],

    # Legal
    "courtroom": ["federal courthouse interior", "courtroom legal", "justice court"],
    "courthouse": ["federal courthouse exterior", "courthouse steps", "justice building"],
    "arrest": ["FBI arrest", "handcuffs arrest", "law enforcement"],
    "trial": ["courtroom trial", "legal proceedings", "federal court"],
    "prison": ["federal prison exterior", "prison fence", "correctional facility"],
    "sentenced": ["prison cell", "federal prison", "incarceration"],

    # Media
    "news": ["news reporter broadcasting", "breaking news studio", "journalist reporting"],
    "media": ["press conference", "media coverage", "news cameras"],
    "investigation": ["journalist investigation", "reporter documents", "news investigation"],

    # General
    "rise": ["business success growth", "corporate rise", "entrepreneur success"],
    "collapse": ["financial crisis", "stock market crash", "economic collapse"],
    "aftermath": ["empty office", "closed business", "economic aftermath"],
    "victim": ["worried people", "financial stress", "people concerned"],
    "new_york": ["New York City skyline", "Manhattan aerial", "NYC financial district"],
    "wall_street": ["Wall Street sign", "financial district walking", "New York Stock Exchange"],
}


def search_videos(query: str, per_page: int = 5, orientation: str = "landscape") -> List[Dict]:
    """Search Pexels for videos matching query."""
    try:
        r = httpx.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "per_page": per_page, "orientation": orientation},
            headers=HEADERS, timeout=15.0,
        )
        if r.status_code == 200:
            return r.json().get("videos", [])
        else:
            logger.warning(f"[pexels] Search failed {r.status_code}: {query}")
    except Exception as e:
        logger.warning(f"[pexels] Search error: {e}")
    return []


def get_best_video_url(video: Dict, min_width: int = 1280) -> Optional[str]:
    """Get best quality video URL from Pexels video object."""
    files = video.get("video_files", [])
    # Sort by resolution descending
    files_sorted = sorted(files, key=lambda f: f.get("width", 0), reverse=True)
    # Prefer HD that fits our target
    for f in files_sorted:
        w = f.get("width", 0)
        if w >= min_width:
            return f.get("link")
    # Fallback to any
    if files_sorted:
        return files_sorted[0].get("link")
    return None


def download_video(url: str, output_path: str) -> bool:
    """Download a video file from URL."""
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as r:
            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                size = os.path.getsize(output_path)
                if size > 1000:
                    logger.debug(f"[pexels] Downloaded: {os.path.basename(output_path)} ({size//1024}KB)")
                    return True
    except Exception as e:
        logger.warning(f"[pexels] Download failed: {e}")
    return False


def scene_to_query(scene: Dict, variation: int = 0) -> str:
    """Convert a storyboard scene to the best Pexels search query.
    variation: used to get different clips for same scene type."""
    action = (scene.get("action") or "").lower()
    title = (scene.get("title") or "").lower()
    location = (scene.get("location") or "").lower()
    act = (scene.get("act") or "").lower()
    narrative = (scene.get("narrative_purpose") or "").lower()
    sd_prompt = (scene.get("sd_scene_prompt") or "").lower()

    combined = f"{action} {title} {location} {narrative} {sd_prompt}"

    # Specific title/action matching first
    title_queries = {
        "beginning": ["young entrepreneur office", "startup business 1960s", "business founding"],
        "founding": ["business launch startup", "company founding", "entrepreneur signing"],
        "nasdaq": ["stock exchange floor", "nasdaq trading", "financial exchange"],
        "ponzi": ["financial fraud documents", "fake investment", "money laundering"],
        "chairman": ["business leader speaking", "executive boardroom", "corporate chairman"],
        "sec": ["government investigation", "federal investigation documents", "regulatory agency"],
        "trouble": ["financial stress", "business problems", "worried businessman"],
        "crisis": ["financial crisis 2008", "stock market crash", "economic collapse"],
        "tipping": ["bankruptcy documents", "financial collapse warning", "crisis meeting"],
        "confession": ["man confessing", "emotional confrontation", "serious conversation"],
        "arrest": ["FBI arrest handcuffs", "law enforcement arrest", "federal agents"],
        "trial": ["courtroom trial", "federal court proceedings", "legal defense"],
        "sentenced": ["judge sentencing", "courtroom verdict", "federal sentencing"],
        "prison": ["federal prison exterior", "prison facility", "correctional institution"],
        "aftermath": ["empty Wall Street", "financial ruin", "victims financial loss"],
        "victims": ["upset people financial loss", "worried investors", "retirement savings loss"],
        "legacy": ["Wall Street sign", "financial district empty", "economic lesson"],
    }

    for key, queries in title_queries.items():
        if key in title:
            q_list = queries
            return q_list[variation % len(q_list)]

    # Check scene type map
    for key, queries in SCENE_QUERY_MAP.items():
        if key in combined:
            return queries[variation % len(queries)]

    # Location-based
    if "wall street" in location or "trading" in location:
        opts = ["Wall Street trading floor", "stock market traders", "financial district walking"]
        return opts[variation % len(opts)]
    if "courtroom" in location or "court" in location:
        opts = ["federal courtroom", "legal proceedings court", "courthouse interior"]
        return opts[variation % len(opts)]
    if "office" in location or "headquarters" in location:
        opts = ["executive office Manhattan", "corporate boardroom meeting", "businessman office"]
        return opts[variation % len(opts)]
    if "prison" in location or "jail" in location:
        opts = ["federal prison", "prison exterior", "correctional facility"]
        return opts[variation % len(opts)]
    if "news" in location or "studio" in location:
        opts = ["news studio broadcasting", "breaking news reporter", "television news anchor"]
        return opts[variation % len(opts)]

    # Act-based with variation
    act_opts = {
        "rise": ["business success entrepreneur", "financial growth prosperity", "corporate success"],
        "cracks": ["business problems stress", "financial warning signs", "corporate scandal"],
        "evidence": ["financial documents investigation", "fraud evidence", "paper trail money"],
        "collapse": ["financial crisis collapse", "stock market crash", "economic disaster"],
        "aftermath": ["empty office aftermath", "financial ruin victims", "economic consequences"],
    }
    for act_key, opts in act_opts.items():
        if act_key in act:
            return opts[variation % len(opts)]

    # Final fallback with variation
    fallbacks = ["financial district New York", "Wall Street business", 
                 "corporate America", "banking finance", "money investment"]
    return fallbacks[variation % len(fallbacks)]


def fetch_scene_footage(
    scenes: List[Dict],
    footage_dir: str,
    max_per_scene: int = 2,
) -> Dict[int, List[str]]:
    """
    Fetch stock footage for all storyboard scenes.
    Returns dict: {scene_number: [video_path1, video_path2]}
    Groups similar scenes to avoid redundant downloads.
    """
    os.makedirs(footage_dir, exist_ok=True)

    # Cache: query → downloaded paths (avoid re-downloading same footage)
    query_cache: Dict[str, List[str]] = {}
    scene_footage: Dict[int, List[str]] = {}

    # Load existing manifest if any
    manifest_path = os.path.join(footage_dir, "manifest.json")
    if os.path.exists(manifest_path):
        try:
            scene_footage = {int(k): v for k, v in json.load(open(manifest_path)).items()}
            logger.info(f"[pexels] Loaded manifest: {len(scene_footage)} scenes cached")
        except Exception:
            pass

    for scene in scenes:
        scene_num = scene.get("scene_number", scene.get("n", 0))
        if scene_num in scene_footage and scene_footage[scene_num]:
            continue  # Already have footage

        variation = scene.get("scene_number", scene.get("n", 0)) % 5
        query = scene_to_query(scene, variation)
        logger.info(f"[pexels] Scene {scene_num}: '{query}'")

        # Check cache first
        if query in query_cache:
            scene_footage[scene_num] = query_cache[query]
            continue

        # Search and download
        videos = search_videos(query, per_page=5)
        if not videos:
            # Try broader fallback
            videos = search_videos("financial business", per_page=3)

        paths = []
        for i, video in enumerate(videos[:max_per_scene]):
            url = get_best_video_url(video)
            if not url:
                continue
            fname = f"scene_{scene_num:03d}_v{i+1}.mp4"
            path = os.path.join(footage_dir, fname)
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                paths.append(path)
                continue
            if download_video(url, path):
                paths.append(path)
            time.sleep(0.3)  # Rate limit

        scene_footage[scene_num] = paths
        query_cache[query] = paths

        # Save manifest periodically
        if scene_num % 5 == 0:
            json.dump(scene_footage, open(manifest_path, "w"), indent=2)

        time.sleep(0.5)

    # Final manifest save
    json.dump(scene_footage, open(manifest_path, "w"), indent=2)
    total = sum(len(v) for v in scene_footage.values())
    logger.info(f"[pexels] Complete: {total} clips for {len(scene_footage)} scenes")
    return scene_footage
