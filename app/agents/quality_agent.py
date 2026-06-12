"""
Quality Agent
Validates scripts and videos before they enter the publish queue.
"""
import logging
import os
import re
import yaml
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from app.models import Script, Video, Topic
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)
import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
SAFETY_PATH = _REPO_ROOT / "config" / "safety_rules.yaml"
PROMPT_PATH = _REPO_ROOT / "app" / "prompts" / "quality_review.md"


def load_rules() -> dict:
    try:
        with open(SAFETY_PATH) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def quick_script_check(script: Script, rules: dict) -> Tuple[bool, List[str], int]:
    """
    Fast deterministic checks. Returns (pass, issues, score_deductions).
    """
    issues = []
    deductions = 0

    if not script.title or len(script.title.strip()) < 5:
        issues.append("Title too short or missing")
        deductions += 30

    text = script.script_text or ""
    wc = len(re.findall(r'\w+', text))
    min_words = rules.get("quality_thresholds", {}).get("min_script_words", 600)

    if wc < min_words:
        issues.append(f"Script too short: {wc} words (min {min_words})")
        deductions += 25

    # Check for banned phrases
    text_lower = text.lower()
    for phrase in rules.get("banned_phrases_in_script", []):
        if phrase.lower() in text_lower:
            issues.append(f"Banned phrase: '{phrase}'")
            deductions += 40

    for phrase in rules.get("financial_claim_patterns", []):
        if re.search(r'\b' + re.escape(phrase.lower()) + r'\b', text_lower):
            issues.append(f"Financial risk phrase: '{phrase}'")
            deductions += 30

    for phrase in rules.get("copyright_risk_terms", []):
        if phrase.lower() in text_lower:
            issues.append(f"Copyright risk term: '{phrase}'")
            deductions += 20

    # Check for duplicate paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    if paragraphs:
        unique_para = set(p[:100] for p in paragraphs)
        dup_ratio = 1 - (len(unique_para) / len(paragraphs))
        max_dup = rules.get("quality_thresholds", {}).get("max_duplicate_paragraph_ratio", 0.25)
        if dup_ratio > max_dup:
            issues.append(f"Too many duplicate paragraphs: {dup_ratio:.0%}")
            deductions += 20

    return len(issues) == 0, issues, deductions


def llm_quality_review(script: Script) -> Tuple[int, List[str], str]:
    """
    Use Ollama to score the script quality.
    Returns (score, issues, recommendation).
    """
    if not ollama_client.is_available():
        return 70, [], "approve"  # Default if no LLM

    try:
        with open(str(PROMPT_PATH)) as f:
            prompt_template = f.read()
    except Exception:
        return 70, [], "approve"

    prompt = (prompt_template
              .replace("{{title}}", script.title or "")
              .replace("{{script_text}}", (script.script_text or "")[:3000]))

    result = ollama_client.generate_json(prompt, temperature=0.1)

    if not result:
        return 70, [], "approve"

    score = int(result.get("total_score", 70))
    issues = result.get("issues", [])
    rec = result.get("recommendation", "approve")
    return score, issues, rec


def run_quality_check(
    script: Script,
    video: Optional[Video],
    db: Session,
) -> Tuple[bool, float, str]:
    """
    Full quality check. Returns (passed, score, reason).
    """
    rules = load_rules()
    min_score = rules.get("quality_thresholds", {}).get("min_quality_score", 75)

    # Fast checks
    fast_pass, fast_issues, deductions = quick_script_check(script, rules)

    if not fast_pass and deductions >= 50:
        reason = "; ".join(fast_issues)
        score = max(0, 100 - deductions)
        if video:
            video.quality_score = score
            video.status = "rejected"
            video.rejection_reason = reason
            db.flush()
        logger.info(f"[quality] REJECTED: {reason}")
        return False, score, reason

    # LLM review
    llm_score, llm_issues, rec = llm_quality_review(script)
    final_score = max(0, llm_score - deductions)

    all_issues = fast_issues + llm_issues
    reason = "; ".join(all_issues) if all_issues else ""

    passed = final_score >= min_score and rec != "reject"

    if video:
        video.quality_score = final_score
        video.status = "approved" if passed else "rejected"
        if not passed:
            video.rejection_reason = reason or f"Score {final_score} below threshold {min_score}"
        db.flush()

    logger.info(f"[quality] score={final_score} passed={passed} reason={reason[:80]}")
    return passed, final_score, reason


def run_quality_phase(
    db: Session,
    topics: List[Topic],
) -> dict:
    """Run quality checks for all packaged topics."""
    results = {"approved": 0, "rejected": 0}

    for topic in topics:
        script = db.query(Script).filter(Script.topic_id == topic.id).first()
        video = db.query(Video).filter(Video.topic_id == topic.id).first()

        if not script:
            continue

        passed, score, reason = run_quality_check(script, video, db)
        if passed:
            results["approved"] += 1
            topic.status = "quality_approved"
        else:
            results["rejected"] += 1
            topic.status = "quality_rejected"

    db.flush()
    logger.info(f"[quality] Approved: {results['approved']}, Rejected: {results['rejected']}")
    return results
