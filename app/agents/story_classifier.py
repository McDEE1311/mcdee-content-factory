"""
Story Classifier + Narrative DNA
Classifies story type and extracts narrative structure before scripting.
"""
import logging
from typing import Dict
logger = logging.getLogger(__name__)


def classify_and_extract_dna(topic: str, research: Dict) -> Dict:
    """Classify story type and extract narrative DNA for script generation."""
    from app.services.ollama_client import ollama_client

    facts = "\n".join(f"- {f[:150]}" for f in research.get("key_facts", [])[:6])
    timeline = "\n".join(
        f"- {e.get('year','')}: {e.get('title','')} — {e.get('description','')[:80]}"
        for e in research.get("timeline", [])[:8]
    )

    prompt = f"""Analyze this documentary topic for story structure.

Topic: "{topic}"

Key facts:
{facts}

Timeline:
{timeline}

Output ONLY this JSON:
{{
  "story_type": "fraud|rise_and_fall|investigation|mystery|disaster|survival|character_study|cautionary_tale",
  "central_tension": "the core conflict in one sentence",
  "viewer_question": "the question that keeps viewers watching",
  "main_character_goal": "what the protagonist was trying to achieve",
  "main_obstacle": "what stopped them or what went wrong",
  "central_contradiction": "the gap between public narrative and reality",
  "stakes": "what was at risk — be specific with numbers if known",
  "turning_points": ["key moment 1", "key moment 2", "key moment 3"],
  "reveals": ["revelation 1", "revelation 2"],
  "consequences": "what happened as a result",
  "lesson": "what this story teaches about human nature",
  "emotional_arc": "curiosity → hope → doubt → shock → understanding",
  "strongest_hook_angle": "the single most compelling entry point for the story"
}}"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.3)
        if result and result.get("story_type"):
            logger.info(f"[classifier] Type: {result['story_type']} | "
                       f"Question: {result.get('viewer_question','')[:60]}")
            return result
    except Exception as e:
        logger.warning(f"[classifier] Failed: {e}")

    return {
        "story_type": "cautionary_tale",
        "central_tension": "public success hiding private failure",
        "viewer_question": "How did nobody stop this sooner?",
        "strongest_hook_angle": "The gap between the story told publicly and what was really happening",
        "emotional_arc": "curiosity → hope → doubt → shock → understanding",
    }
