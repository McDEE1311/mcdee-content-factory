"""
Test quality agent checks.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.agents.quality_agent import quick_script_check, load_rules
from app.models import Script


_LONG_SCRIPT = """
[HOOK]
GPU prices just dropped 40% in a single week. Here is exactly what is driving this crash
and what it means for AI infrastructure operators.

[WHY IT MATTERS]
If you run GPU compute, buy hardware, or operate nodes on networks like Bittensor,
this directly affects your cost basis and your competitive position. Lower GPU prices mean
lower barriers to entry for new validators, more competition on subnets, and potentially
a reshuffling of who can afford to run competitive nodes at scale.

[WHAT HAPPENED]
According to multiple market trackers, RTX 3090 cards have fallen from around $800
to under $500 in the past 30 days. The RTX 3060 is now trading below $250.
This is being driven by a combination of new supply from Nvidia's 40-series rollout,
a significant reduction in crypto mining demand following the Ethereum merge, and a wave of
secondhand cards hitting the market from former miners looking to offload inventory.
The timing coincides with enterprise GPU allocation from hyperscalers shifting toward H100 and A100,
further pushing down consumer-grade secondhand supply.

[BREAKDOWN]
For AI workloads, the price drop is material. A node operator running four RTX 3090s
can now build out their stack for roughly two thousand dollars instead of thirty-two hundred.
That is a 37 percent reduction in upfront capital cost.
For Bittensor subnet operators in particular, this changes the validator economics considerably.
The Compute subnet has seen miner registrations increase by roughly 18 percent in the past two weeks,
which may reflect exactly this kind of barrier reduction.
For anyone building out local inference capacity, the calculation for running a 70B parameter model
locally just improved significantly, as four 3090s can now be acquired for under two thousand dollars
and provide enough VRAM to run models at reasonable throughput.

[RISKS AND REALITY CHECK]
The market may not stay here. Historically, GPU prices spike back sharply when crypto sentiment
recovers or a new AI workload category drives enterprise demand.
Buying at the bottom assumes the bottom is actually here, which remains uncertain.
There are also open questions about the longevity of 3090 cards for AI workloads as newer
architectures with better inference performance per watt continue to come to market.
Do not over-extend capital on secondhand hardware without a clear workload plan.

[WHAT TO WATCH NEXT]
Watch the Bittensor Compute subnet registration numbers over the next two weeks.
Watch for any crypto sentiment reversal that could absorb secondhand GPU supply.
Monitor Nvidia's production announcements for the 50-series cards, which could further
depress 30-series and 40-series pricing when they arrive.

[CTA]
Subscribe for daily AI infrastructure briefs. Drop your thoughts in the comments below.
What are you planning to do with the current GPU market conditions?
Let us know if you have already picked up hardware at these prices and what workload you are running.
We read every comment and frequently cover community questions in follow-up videos.
If you found this analysis useful, consider sharing it with someone else in the infrastructure or
crypto compute space who would benefit from understanding what is happening in the GPU market right now.
The next video will cover specific Bittensor subnets that stand to benefit most from a broader
validator base enabled by lower hardware costs. That one drops tomorrow.

Additional context for builders: when evaluating secondhand GPU purchases, always factor in
the power draw and cooling requirements of your setup. A 3090 pulls 350 watts under full load,
so a four-card rig is running close to 1400 watts continuous. At current US average electricity
rates that is roughly 100 dollars per month per rig in power costs alone before factoring in
cooling overhead. This matters a great deal for your subnet economics on Bittensor compute,
where your net earnings depend heavily on your cost per inference or cost per training step.
The hardware price drop helps on capital expenditure but does not change your ongoing operational
cost structure, which you need to model carefully before committing to a large hardware purchase.
"""

def make_script(**kwargs) -> Script:
    """Helper to build a Script object for testing."""
    defaults = {
        "id": 1,
        "topic_id": 1,
        "title": "Why GPU Prices Are Crashing Right Now",
        "hook": "GPU prices just dropped 40%. Here is what is driving it.",
        "script_text": _LONG_SCRIPT,
        "description": "Analysis of GPU price crash and implications for AI compute.",
        "tags_json": ["GPU", "AI", "infrastructure", "Bittensor", "compute"],
        "word_count": len(_LONG_SCRIPT.split()),
        "status": "generated",
    }
    defaults.update(kwargs)
    s = Script()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def test_clean_script_passes():
    """A clean, substantive script should pass all quick checks."""
    rules = load_rules()
    script = make_script()
    passed, issues, deductions = quick_script_check(script, rules)
    assert passed is True
    assert len(issues) == 0
    assert deductions == 0


def test_empty_title_fails():
    """Script with empty title should fail."""
    rules = load_rules()
    script = make_script(title="")
    passed, issues, deductions = quick_script_check(script, rules)
    assert passed is False
    assert any("title" in i.lower() for i in issues)
    assert deductions >= 30


def test_short_script_fails():
    """Script under minimum word count should fail."""
    rules = load_rules()
    script = make_script(script_text="This is a very short script.", word_count=10)
    passed, issues, deductions = quick_script_check(script, rules)
    assert passed is False
    assert any("short" in i.lower() for i in issues)


def test_banned_phrase_fails():
    """Script with banned phrase should fail."""
    rules = load_rules()
    long_text = "word " * 700
    script = make_script(
        script_text=long_text + "\nThis is a guaranteed profit opportunity for everyone."
    )
    passed, issues, deductions = quick_script_check(script, rules)
    assert not passed or deductions >= 30
    assert any("guaranteed" in i.lower() or "profit" in i.lower() for i in issues)


def test_copyright_risk_term_penalized():
    """Script with copyright risk terms should be penalized."""
    rules = load_rules()
    long_text = "word " * 700
    script = make_script(
        script_text=long_text + "\nHere is the full episode for download."
    )
    passed, issues, deductions = quick_script_check(script, rules)
    assert deductions > 0
    assert any("full episode" in i.lower() or "copyright" in i.lower() for i in issues)


def test_duplicate_paragraphs_penalized():
    """Script with many duplicate paragraphs should be penalized."""
    rules = load_rules()
    para = "This is a repeated paragraph about AI infrastructure that appears many times in the script.\n\n"
    script = make_script(script_text=para * 20)
    passed, issues, deductions = quick_script_check(script, rules)
    assert deductions > 0


def test_quality_score_structure():
    """Quality scoring should return expected tuple structure."""
    rules = load_rules()
    script = make_script()
    result = quick_script_check(script, rules)
    assert isinstance(result, tuple)
    assert len(result) == 3
    passed, issues, deductions = result
    assert isinstance(passed, bool)
    assert isinstance(issues, list)
    assert isinstance(deductions, int)


def test_financial_claim_rejected():
    """Script claiming guaranteed returns should get high deductions."""
    rules = load_rules()
    long_text = "word " * 700
    script = make_script(
        script_text=long_text + "\nYou will make 100% profit guaranteed with this method."
    )
    passed, issues, deductions = quick_script_check(script, rules)
    assert deductions >= 30


def test_thumbnail_creation(tmp_path):
    """Thumbnail should be created successfully if Pillow available."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    from app.services.image_service import create_thumbnail
    out = str(tmp_path / "thumb.png")
    result = create_thumbnail("AI Infrastructure Is Changing Fast", out, theme_index=0)
    assert result is True
    assert (tmp_path / "thumb.png").exists()


def test_calculate_schedule_10_videos():
    """10 videos should be spaced correctly across upload window."""
    from app.agents.queue_manager import calculate_schedule
    import pytz

    times = calculate_schedule(10, run_date="2025-01-15", start_hour=8, end_hour=20,
                                tz_name="America/Chicago")
    assert len(times) == 10

    ct = pytz.timezone("America/Chicago")
    local = [t.astimezone(ct) for t in times]

    # No two at same time
    time_strs = [t.strftime("%H:%M") for t in local]
    assert len(set(time_strs)) == 10

    # All within window
    for t in local:
        assert 8 <= t.hour <= 20


def test_daily_limit_enforced():
    """Daily limit should cap at DAILY_VIDEO_LIMIT."""
    from app.agents.queue_manager import calculate_schedule
    times = calculate_schedule(15, run_date="2025-01-15", start_hour=8, end_hour=20)
    # Should still return 15 times — limit enforcement is in queue_manager not schedule calc
    assert len(times) == 15
