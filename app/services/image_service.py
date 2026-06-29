"""
Image service - generates thumbnails and background images using Pillow.
"""
import logging
import os
import textwrap
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Color presets for thumbnails
THUMBNAIL_THEMES = [
    {"bg": (15, 15, 25), "accent": (0, 200, 255), "text": (255, 255, 255)},
    {"bg": (20, 10, 30), "accent": (180, 0, 255), "text": (255, 255, 255)},
    {"bg": (5, 20, 5), "accent": (0, 255, 100), "text": (255, 255, 255)},
    {"bg": (25, 10, 5), "accent": (255, 120, 0), "text": (255, 255, 255)},
    {"bg": (10, 20, 30), "accent": (0, 150, 255), "text": (230, 230, 255)},
]


def create_thumbnail(
    title: str,
    output_path: str,
    width: int = 1280,
    height: int = 720,
    theme_index: int = 0,
) -> bool:
    """
    Create a simple high-contrast YouTube thumbnail using Pillow.
    Returns True on success.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("[image] Pillow not installed, cannot create thumbnail.")
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    theme = THUMBNAIL_THEMES[theme_index % len(THUMBNAIL_THEMES)]
    bg_color = theme["bg"]
    accent_color = theme["accent"]
    text_color = theme["text"]

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw accent bar at left
    draw.rectangle([(0, 0), (12, height)], fill=accent_color)

    # Draw accent line at bottom
    draw.rectangle([(0, height - 8), (width, height)], fill=accent_color)

    # Draw diagonal grid lines (subtle)
    for i in range(0, width + height, 80):
        draw.line([(i, 0), (i - height, height)], fill=(255, 255, 255, 15), width=1)

    # Try to load a font
    font_large = _load_font(size=72)
    font_small = _load_font(size=36)

    # Wrap title text
    clean_title = title.strip().upper()
    wrapped = textwrap.wrap(clean_title, width=22)
    if len(wrapped) > 3:
        wrapped = wrapped[:3]

    # Calculate text block height
    line_height = 85
    total_text_height = len(wrapped) * line_height
    y_start = (height - total_text_height) // 2 - 20

    for i, line in enumerate(wrapped):
        y = y_start + i * line_height
        # Shadow
        draw.text((44, y + 4), line, font=font_large, fill=(0, 0, 0))
        # Main text
        draw.text((42, y), line, font=font_large, fill=text_color)

    # Bottom label
    draw.text((42, height - 60), "McDEE • DAILY TREND BRIEF", font=font_small, fill=accent_color)

    img.save(output_path, "PNG", optimize=True)
    logger.info(f"[image] Thumbnail saved: {output_path}")
    return True


def _load_font(size: int = 64):
    """Load best available font."""
    try:
        from PIL import ImageFont
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in font_paths:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def create_background_frame(
    width: int = 1920,
    height: int = 1080,
    color: Tuple = (10, 10, 20),
    output_path: str = None,
) -> Optional[object]:
    """Create a simple dark background frame for video."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (width, height), color)
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path)
        return img
    except Exception as e:
        logger.warning(f"[image] Could not create background: {e}")
        return None
