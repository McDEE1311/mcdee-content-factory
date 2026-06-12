# Thumbnail Concept Prompt

Generate a YouTube thumbnail concept for this video.

## Video Info
Title: {{title}}
Niche: {{niche}}

## Thumbnail Requirements
- 1280x720 pixels
- High contrast text on dark background
- Bold, readable from small size
- One clear visual element or icon concept
- No cluttered text

## Output Format
Return ONLY valid JSON:
```json
{
  "headline_text": "3-5 words for the thumbnail (bold)",
  "subtext": "optional 2-3 word subtext",
  "visual_concept": "Description of background visual or icon",
  "color_scheme": "dark_blue / dark_green / dark_purple / dark_orange",
  "emoji_accent": "one relevant emoji if any"
}
```
