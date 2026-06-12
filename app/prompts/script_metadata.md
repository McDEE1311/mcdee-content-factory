# Script Metadata Prompt

Given a YouTube script, generate the video metadata as JSON.

## Script Title / Topic
{{title}}

## Script Excerpt
{{excerpt}}

## Output
Return ONLY valid JSON:
{
  "title": "YouTube title max 90 chars",
  "description": "300-400 word YouTube description with timestamps",
  "tags": ["tag1", "tag2", ...],
  "thumbnail_prompt": "thumbnail visual concept",
  "x_post": "X post max 240 chars ending with [LINK]"
}
