"""
Script Agent V5
Generates documentary script FROM storyboard events.
Research → Storyboard → Script (not Script → Storyboard)
"""
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_V5 = """You are a master documentary scriptwriter for Trend Forge, a premium YouTube documentary channel.
Your scripts feel like Netflix true crime documentaries — not Wikipedia summaries.

CRITICAL RULES:
1. HOOK: Open mid-action with the most shocking specific moment. Never introduce context first.
2. EMOTION: Every paragraph must have emotional weight — betrayal, panic, greed, triumph, despair.
3. OPEN LOOPS: End every section with unresolved tension pulling viewers forward.
4. SPECIFICITY: Use real names, real dates, real places. No vague generalities.
5. HUMAN COST: Always connect events to real people affected.
6. PACING: Short punchy sentences during dramatic moments. Longer sentences for context.
7. ACCURACY: Use "reportedly", "according to accounts", "sources suggest" for uncertain claims.

You are writing FROM a storyboard. Every scene in the storyboard must be reflected in the script.
The script narrates what the viewer is seeing on screen."""


def generate_script_from_storyboard(
    topic: str,
    category: str,
    research: Dict,
) -> str:
    """
    Generate full documentary script from storyboard events.
    The storyboard is the source of truth — script narrates what storyboard shows.
    """
    from app.services.ollama_client import ollama_client

    storyboard = research.get("storyboard", [])
    characters = research.get("characters", {})
    timeline = research.get("timeline", [])
    key_facts = research.get("key_facts", [])

    # Load writing style rules
    never_str = ""
    try:
        import yaml as _yaml, pathlib as _pl
        _sf = _pl.Path(__file__).parent.parent.parent / "config" / "trendforge_writing_style.yaml"
        _style = _yaml.safe_load(open(str(_sf)))
        _never = _style.get("rules", {}).get("NEVER", [])
        never_str = "\n".join(f"- NEVER: {n}" for n in _never[:8])
    except Exception:
        never_str = "- NEVER use 'In today\'s video'\n- NEVER use 'little did they know'"

    # Load writing style rules
    never_str = ""
    try:
        import yaml as _yaml, pathlib as _pl
        _sf = _pl.Path(__file__).parent.parent.parent / "config" / "trendforge_writing_style.yaml"
        _style = _yaml.safe_load(open(str(_sf)))
        _never = _style.get("rules", {}).get("NEVER", [])
        never_str = "\n".join(f"- NEVER: {n}" for n in _never[:8])
    except Exception:
        never_str = "- NEVER use 'In today\'s video'\n- NEVER use 'little did they know'"

    # Build character reference
    char_ref = "\n".join([
        f"- {v['name']}: {v.get('sd_character_prompt', '')[:100]}"
        for v in characters.values()
    ])

    # Build timeline reference
    timeline_ref = "\n".join([
        f"- {e.get('year', '')}: {e.get('title', '')} — {e.get('description', '')[:80]}"
        for e in timeline[:12]
    ])

    # Build fact reference
    facts_ref = "\n".join(f"- {f[:150]}" for f in key_facts[:8])

    # Group storyboard by act
    acts = {}
    for scene in storyboard:
        act = scene.get("act", "EVIDENCE")
        if act not in acts:
            acts[act] = []
        acts[act].append(scene)

    # Generate each act as a script section
    act_order = ["RISE", "CRACKS", "EVIDENCE", "COLLAPSE", "AFTERMATH"]
    parts = []
    total_words = 0
    prev_context = ""

    # HOOK — use hook engine to generate best scored hook
    logger.info("[script_v5] Running hook engine...")
    try:
        from app.agents.hook_agent import get_best_hook, build_story_thesis
        best_hook = get_best_hook(topic, research)
        thesis = build_story_thesis(topic, research, best_hook)
        hook_text = best_hook.get("hook_text", "")
        logger.info(f"[script_v5] Hook score: {best_hook.get('total_score', 0)} | "
                    f"{best_hook.get('opening_line', '')[:60]}")
        logger.info(f"[script_v5] Thesis: {thesis.get('one_sentence_thesis', '')[:80]}")
    except Exception as e:
        logger.warning(f"[script_v5] Hook engine failed: {e}, using fallback")
        hook_text = ""
        thesis = {"one_sentence_thesis": f"The story of {topic}.", "central_question": "How did nobody stop this?"}

    if not hook_text:
        # Generate directly as fallback
        hook_prompt = f'''Write a 4-5 sentence documentary hook for: "{topic}"
Start with a shocking specific fact. Create immediate unanswered question.
DO NOT start with "Today" or "In this video". 
Write ONLY the hook text, no headers:'''
        try:
            hook_text = ollama_client.generate(
                hook_prompt, system=SYSTEM_PROMPT_V5,
                temperature=0.85, max_tokens=200, timeout=120.0
            ).strip()
        except Exception:
            hook_text = "What you are about to hear is one of the most remarkable stories of deception in modern history."

    parts.append("[HOOK]\n" + hook_text)
    prev_context = hook_text
    total_words += len(hook_text.split())
    logger.info(f"[script_v5] HOOK: {len(hook_text.split())} words")
    
    # Add thesis to context so all sections refer back to it
    thesis_context = f"STORY THESIS: {thesis.get('one_sentence_thesis', '')}\nCENTRAL QUESTION: {thesis.get('central_question', '')}"

    # Generate each act
    for act in act_order:
        scenes = acts.get(act, [])
        if not scenes:
            continue

        scene_descriptions = "\n".join([
            f"Scene {s.get('scene_number', i+1)}: {s.get('action', '')} "
            f"[{s.get('emotion', '')}] — {s.get('narrative_purpose', '')}"
            for i, s in enumerate(scenes[:8])
        ])

        act_prompts = {
            "RISE": (
                "Write the [THE RISE] section. 500-650 words. "
                "Show the protagonist at their absolute peak. Make us almost believe the dream. "
                "Use specific names, amounts, dates from the storyboard. "
                "End with subtle hint that something is wrong underneath."
            ),
            "CRACKS": (
                "Write the [THE CRACKS] section. 500-650 words. "
                "Show warning signs being ignored. Focus on DENIAL and HOPE overriding logic. "
                "Show who raised concerns and why they were dismissed. "
                "Build dread. End with open loop."
            ),
            "EVIDENCE": (
                "Write the [THE EVIDENCE] section. 600-750 words. "
                "The factual spine. Walk through key decisions and revelations. "
                "Humanize the numbers — show real human cost. "
                "Use 'reportedly' and 'according to accounts' for uncertain claims. "
                "End with: 'And then came the moment that changed everything.'"
            ),
            "COLLAPSE": (
                "Write the [THE COLLAPSE] section. 500-650 words. "
                "The moment everything fell apart publicly. "
                "Fast pace — short sentences during dramatic moments. "
                "Show the timeline hour by hour. Show human panic and disbelief. "
                "End at the point of no return."
            ),
            "AFTERMATH": (
                "Write the [THE AFTERMATH] section and [WHAT THIS MEANS] and [CTA]. "
                "500-600 words total. Show who paid the price vs who was responsible. "
                "One clear insight about human nature. "
                "End CTA with one provocative question that makes viewers comment."
            ),
        }

        prompt = f"""Documentary: "{topic}"
Category: {category}

{thesis_context}

WRITING STYLE RULES:
{never_str}
Every section must end with unresolved tension or open question.

STORYBOARD SCENES FOR THIS SECTION ({act}):
{scene_descriptions}

KEY FACTS:
{facts_ref[:400]}

CHARACTERS:
{char_ref[:300]}

TIMELINE CONTEXT:
{timeline_ref[:300]}

Previous script context:
{prev_context[-500:] if prev_context else "Beginning of documentary."}

{act_prompts.get(act, f"Write the [{act}] section. 500-600 words.")}

Write ONLY this section. Start with the section header [{act}].
Reference the storyboard scenes above. Make it feel like narrating what the viewer sees."""

        try:
            result = ollama_client.generate(
                prompt, system=SYSTEM_PROMPT_V5,
                temperature=0.75, max_tokens=1400, timeout=360.0
            ).strip()
            wc = len(result.split())
            parts.append(result)
            prev_context = result[-600:]
            total_words += wc
            logger.info(f"[script_v5] {act}: {wc} words (total: {total_words})")
        except Exception as e:
            logger.warning(f"[script_v5] {act} failed: {e}")
            parts.append(f"[{act}]\n[Section generation failed — retrying on next run]")

    script = "\n\n".join(parts)
    logger.info(f"[script_v5] Complete: {total_words} words")
    return script


def build_scene_prompts_v5(
    storyboard: List[Dict],
    characters: Dict,
    category: str,
) -> List[Dict]:
    """
    Build SD scene prompts directly from storyboard events.
    Each prompt is anchored to a specific story moment, not a narration chunk.
    """
    # Base style for category
    styles = {
        "financial_rise_fall": (
            "cinematic documentary illustration, semi-realistic graphic novel style, "
            "dramatic corporate atmosphere, high detail expressive faces, "
            "strong dramatic shadows, Netflix true crime documentary quality, "
        ),
        "historical_mystery": (
            "cinematic historical documentary illustration, semi-realistic style, "
            "warm candlelight atmosphere, 18th century European setting, "
            "dramatic chiaroscuro lighting, Netflix documentary quality, "
        ),
        "dark_history": (
            "cinematic historical documentary illustration, semi-realistic style, "
            "dramatic moody atmosphere, high detail faces, documentary quality, "
        ),
        "survival_stories": (
            "cinematic survival documentary illustration, semi-realistic style, "
            "dramatic tense atmosphere, harsh natural lighting, documentary quality, "
        ),
        "space_mysteries": (
            "cinematic space documentary illustration, deep cosmic atmosphere, "
            "dramatic scale, scientific visualization quality, "
        ),
    }
    style = styles.get(category, styles["financial_rise_fall"])
    neg = (
        "blurry, watermark, text, letters, numbers, anime, cartoon, "
        "low quality, ugly, deformed, extra fingers, bad anatomy, "
        "wrong gender, oversaturated, plastic skin"
    )

    # Build character lookup for quick injection
    char_lookup = {}
    for key, char in characters.items():
        name = char.get("name", key).lower()
        char_lookup[name] = {
            "prompt": char.get("sd_character_prompt", ""),
            "seed": char.get("sd_seed"),
        }

    prompts = []
    for i, scene in enumerate(storyboard):
        # Get character description if character named in scene
        char_name = scene.get("character", "")
        char_data = None
        if char_name:
            # Find matching character
            for name, data in char_lookup.items():
                if any(part in name for part in char_name.lower().split()):
                    char_data = data
                    break

        # Build the scene prompt
        base_sd = scene.get("sd_scene_prompt", "")

        if base_sd and char_data and char_data.get("prompt"):
            # Inject character description into scene prompt
            char_desc = char_data["prompt"]
            prompt = f"{style}{char_desc}, {base_sd}, no text, no watermark"
        elif base_sd:
            prompt = f"{style}{base_sd}, no text, no watermark"
        else:
            # Fallback from action description
            action = scene.get("action", "documentary scene")
            location = scene.get("location", "")
            emotion = scene.get("emotion", "dramatic")
            prompt = f"{style}{action} at {location}, {emotion} atmosphere, cinematic, no text"

        prompts.append({
            "n": i + 1,
            "scene_number": scene.get("scene_number", i + 1),
            "act": scene.get("act", "EVIDENCE"),
            "title": scene.get("title", f"Scene {i+1}"),
            "character": char_name,
            "sd_prompt": prompt[:480],
            "negative_prompt": neg,
            "seed": char_data["seed"] if char_data else None,
            "importance": scene.get("importance", "supporting"),
            "camera": scene.get("camera", "medium"),
        })

    logger.info(f"[script_v5] Built {len(prompts)} storyboard-driven scene prompts")
    return prompts
