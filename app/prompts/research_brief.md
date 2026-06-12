# Research Brief Prompt

You are a research assistant gathering background information for a YouTube explainer video.

## Topic
Title: {{title}}
Niche: {{niche}}

## Sources Available
{{sources}}

## Instructions
Based on the topic and available sources, produce a research brief.

DO NOT copy source text verbatim. Summarize in your own words.
Identify 5-8 key facts relevant to explaining this topic.
Note any controversy, uncertainty, or risk.

## Output Format
Return ONLY valid JSON:
```json
{
  "summary": "2-3 paragraph summary of the topic",
  "facts": [
    "Fact 1 in one clear sentence",
    "Fact 2...",
    "..."
  ],
  "controversy": "One paragraph on risks, uncertainty, or controversy if any",
  "angle_suggestion": "Suggested content angle for this video"
}
```
