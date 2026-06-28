"""
Hook Agent
Generates 10 hook options before script writing, scores them, returns the best.
The hook is the single most important element for retention.
"""
import json
import logging
import pathlib
import yaml
from typing import Dict, List

logger = logging.getLogger(__name__)
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_STYLE_FILE = _REPO_ROOT / "config" / "trendforge_writing_style.yaml"


def load_style() -> dict:
    with open(str(_STYLE_FILE)) as f:
        return yaml.safe_load(f)


def generate_hooks(topic: str, research: Dict) -> List[Dict]:
    """Generate 10 hook options and score each one."""
    from app.services.ollama_client import ollama_client

    style = load_style()
    formulas = style.get("hook_formulas", {})
    
    # Build context from research
    facts = "\n".join(f"- {f[:150]}" for f in research.get("key_facts", [])[:6])
    timeline = "\n".join(
        f"- {e.get('year','')}: {e.get('title','')} — {e.get('description','')[:80]}"
        for e in research.get("timeline", [])[:6]
    )
    chars = ", ".join(
        v.get("name", k) for k, v in research.get("characters", {}).items()
    )
    
    formula_examples = "\n".join(f"- {k}: {v}" for k, v in formulas.items())

    prompt = f"""You are writing hooks for a documentary: "{topic}"

KEY FACTS:
{facts}

TIMELINE:
{timeline}

MAIN CHARACTERS: {chars}

HOOK FORMULAS TO USE:
{formula_examples}

RULES:
- Never start with "In today's video" or "Today we're looking at"
- Never use "Little did they know"
- Start mid-story with a specific shocking moment, number, or fact
- Create an immediate unanswered question
- 3-5 sentences maximum per hook
- Every hook must make the viewer NEED to keep watching

Generate exactly 10 different hooks for this documentary.
Use different formulas and angles for each.

Output ONLY this JSON:
[
  {{
    "hook_number": 1,
    "formula": "promise_contradiction",
    "hook_text": "the complete hook text here",
    "opening_line": "first sentence only",
    "curiosity_score": 8,
    "stakes_score": 7,
    "clarity_score": 9,
    "retention_score": 8,
    "visual_potential": 7,
    "total_score": 39
  }}
]"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.85)
        if isinstance(result, list) and len(result) > 0:
            # Sort by total score
            result.sort(key=lambda x: x.get("total_score", 0), reverse=True)
            logger.info(f"[hooks] Generated {len(result)} hooks, best score: {result[0].get('total_score', 0)}")
            return result
    except Exception as e:
        logger.warning(f"[hooks] Generation failed: {e}")

    # Fallback hook
    return [{
        "hook_number": 1,
        "formula": "number_shock",
        "hook_text": f"What you are about to hear is one of the most extraordinary stories of deception ever told. And the most shocking part is how long it took for anyone to notice.",
        "opening_line": "What you are about to hear is one of the most extraordinary stories of deception ever told.",
        "total_score": 35,
    }]


def get_best_hook(topic: str, research: Dict) -> Dict:
    """Get the single best hook for this documentary."""
    hooks = generate_hooks(topic, research)
    best = hooks[0] if hooks else {}
    logger.info(f"[hooks] Best hook (score {best.get('total_score', 0)}): {best.get('opening_line', '')[:80]}")
    return best


def build_story_thesis(topic: str, research: Dict, best_hook: Dict) -> Dict:
    """
    Generate the story thesis — what this documentary is REALLY about.
    This becomes the spine that every section refers back to.
    """
    from app.services.ollama_client import ollama_client
    
    facts = "\n".join(f"- {f[:150]}" for f in research.get("key_facts", [])[:5])
    
    prompt = f"""Documentary topic: "{topic}"

KEY FACTS:
{facts}

BEST HOOK: {best_hook.get('hook_text', '')}

A great documentary is never just about the surface topic.
Theranos is not just about fake blood tests — it is about how ambition, media hype, and investor FOMO created a billion-dollar illusion.
FTX is not just about crypto fraud — it is about how one man used the language of altruism to steal from people who trusted him.

Generate the story thesis for THIS documentary.

Output ONLY this JSON:
{{
  "surface_topic": "what the story appears to be about",
  "deeper_truth": "what the story is REALLY about",
  "central_question": "the one question that keeps viewers watching",
  "emotional_arc": "how viewer emotions change from start to end",
  "central_contradiction": "the core irony or contradiction at the heart of the story",
  "viewer_takeaway": "what the viewer understands by the end that they did not at the start",
  "one_sentence_thesis": "the entire story in one powerful sentence"
}}"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.5)
        if result and result.get("one_sentence_thesis"):
            logger.info(f"[thesis] {result['one_sentence_thesis'][:100]}")
            return result
    except Exception as e:
        logger.warning(f"[thesis] Failed: {e}")
    
    return {
        "one_sentence_thesis": f"The story of {topic} is about how the gap between image and reality can survive for years when everyone profits from the illusion.",
        "central_question": "How did nobody stop this sooner?",
        "deeper_truth": "The systems designed to protect people failed them.",
        "emotional_arc": "Fascination → suspicion → horror → understanding",
    }
