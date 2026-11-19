"""Progress maths (core/progress.py, core/trend.py), checked against hand calculations."""

import datetime as dt

import pandas as pd
import pytest

from spotonfit.config import EnergyPolicy
from spotonfit.core.progress import WeekStats, date_phrase, goal_eta, weekly_review
from spotonfit.core.targets import Goal, Profile, compute_targets
from spotonfit.core.trend import blend, gradual, observed_tdee

ME = Profile(age=26, sex="male", height_cm=177.8, weight_kg=92.2, goal=Goal.LOSE_FAT, body_fat_pct=24.0)
DAY0 = dt.date(2026, 11, 1)


def frame(kcal: float, weights: list[float | None]) -> pd.DataFrame:
    days = [DAY0 + dt.timedelta(days=i) for i in range(len(weights))]
    return pd.DataFrame({"day": days, "kcal": [kcal] * len(days), "logged": [True] * len(days), "weight_kg": weights})


def test_learned_tdee_matches_hand_calculation():
    """Technical PRD exit criterion. With alpha = 1 the trend equals the raw weights, so:
    92.0 kg on day 0 -> 91.0 kg on day 20, eating 2,000 kcal/day:
    TDEE = 2000 - (91.0 - 92.0) x 7700 / 20 = 2000 + 385 = 2,385 kcal."""
    weights = [92.0 - i / 20 for i in range(21)]
    obs = observed_tdee(frame(2000, weights), EnergyPolicy(trend_alpha=1.0))
    assert obs["tdee"] == pytest.approx(2385)
    assert obs["avg_intake"] == 2000 and obs["days"] == 20 and obs["logged_days"] == 21

    # Learned value moves gradually: blend 70/30 with the prior, then cap at 100 kcal/week.
    # 0.7 x 2,590 + 0.3 x 2,385 = 2,528.5: a 61.5 kcal move, under the cap, so it stands.
    assert blend(2590, 2385) == pytest.approx(2528.5)
    assert gradual(2590, blend(2590, 2385)) == pytest.approx(2528.5)
    # A bigger jump is capped: 2,590 -> 2,385 would be -205; it moves only -100 this week.
    assert gradual(2590, 2385) == 2490 and gradual(2590, 2800) == 2690


def test_a_warmed_up_trend_removes_the_ema_lag():
    """Losing 0.07 kg/day on 1,950 kcal: true maintenance = 1950 + 0.07 x 7700 = 2,489.
    An EMA started inside the window lags and under-states the loss; the full-history trend
    (6 weeks of weigh-ins before the window) gets close to the truth."""
    from spotonfit.core.trend import weight_trend

    history = [(DAY0 + dt.timedelta(days=i), 95.0 - 0.07 * i) for i in range(63)]
    window = frame(1950, [w for _, w in history[-21:]])
    window["day"] = [d for d, _ in history[-21:]]
    cold = observed_tdee(window)["tdee"]
    warm = observed_tdee(window, full_trend=weight_trend(history))["tdee"]
    assert abs(warm - 2489) < 25 < abs(cold - 2489)


def test_stable_weight_means_maintenance_equals_intake():
    assert observed_tdee(frame(2200, [90.0] * 21))["tdee"] == pytest.approx(2200)


def test_needs_enough_logged_days_and_weigh_ins():
    assert observed_tdee(frame(2000, [90.0] * 10)) is None  # < 14 logged days
    sparse = [90.0 if i % 7 == 0 else None for i in range(21)]  # 3 weigh-ins
    assert observed_tdee(frame(2000, sparse)) is None


def test_goal_eta_is_a_date_range():
    """92 -> 87 kg (5 kg = 38,500 kcal). Maintenance 2,500 +- 150, eating 2,000:
    deficit 350..650 kcal/day -> 60 to 110 days."""
    today = dt.date(2026, 11, 19)
    eta = goal_eta(92.0, 87.0, 2500, 2000, today)
    assert eta["earliest"] == today + dt.timedelta(days=60)
    assert eta["latest"] == today + dt.timedelta(days=110)
    assert eta["message"].startswith("87 kg likely between mid-Jan 2027 and early-Mar 2027")
    assert "not a promise" in eta["message"]

    one_sided = goal_eta(92.0, 87.0, 2500, 2400, today)  # deficit -50..250: only the fast end is known
    assert one_sided["latest"] is None and one_sided["earliest"]
    stuck = goal_eta(92.0, 87.0, 2500, 2700, today)  # eating above maintenance
    assert stuck["on_track"] is False and stuck["earliest"] is None
    assert goal_eta(87.05, 87.0, 2500, 2000, today)["message"].startswith("You're at your goal")


def test_date_phrase():
    assert date_phrase(dt.date(2027, 1, 3)) == "early-Jan 2027"
    assert date_phrase(dt.date(2027, 1, 15)) == "mid-Jan 2027"
    assert date_phrase(dt.date(2027, 1, 28)) == "late-Jan 2027"


def stats(days=7, on_target=6):
    return WeekStats(days_logged=days, avg_kcal=2000, avg_protein=150, avg_steps=6000, on_target_days=on_target,
                     protein_hit_days=5)  # fmt: skip


def test_review_proposes_steps_when_stalled_and_consistent():
    t = compute_targets(ME, week_index=2)
    proposal, _ = weekly_review(stats(), [-0.05, 0.0], 92.0, Goal.LOSE_FAT, t)
    assert proposal["kind"] == "steps" and proposal["delta"] == 1500
    assert "steps a day" in proposal["text"]


def test_review_cuts_kcal_when_steps_are_capped_but_never_below_floor():
    light = Profile(**{**ME.__dict__, "activity": "light"})  # target 2,080, floor 1,884
    capped = compute_targets(light, week_index=30)  # steps at the 10,000 cap
    proposal, _ = weekly_review(stats(), [0.0, 0.0], 92.0, Goal.LOSE_FAT, capped)
    assert (proposal["kind"], proposal["delta"]) == ("kcal", -100)
    at_floor = compute_targets(ME, week_index=30)  # sedentary: 1,809 would be below the floor, so 1,890
    proposal, notes = weekly_review(stats(), [0.0, 0.0], 92.0, Goal.LOSE_FAT, at_floor)
    assert proposal is None and "floor" in notes[0]


def test_review_safety_and_consistency_rules():
    t = compute_targets(ME, week_index=2)
    fast, _ = weekly_review(stats(), [-0.5, -1.2], 92.0, Goal.LOSE_FAT, t)  # 1.3% of body weight in a week
    assert (fast["kind"], fast["delta"]) == ("kcal", 100)
    none, notes = weekly_review(stats(days=3), [0.0, 0.0], 92.0, Goal.LOSE_FAT, t)
    assert none is None and "3 of 7 days" in notes[0]
    sloppy, notes = weekly_review(stats(on_target=2), [0.0, 0.0], 92.0, Goal.LOSE_FAT, t)
    assert sloppy is None and "consisten" in notes[0]
    on_track, notes = weekly_review(stats(), [-0.5, -0.6], 92.0, Goal.LOSE_FAT, t)
    assert on_track is None and "On track" in notes[0]
    first_week, notes = weekly_review(stats(), [0.0], 92.0, Goal.LOSE_FAT, t)  # not enough weeks to call a stall
    assert first_week is None and "Too early" in notes[0]


def test_review_for_muscle_gain():
    t = compute_targets(Profile(**{**ME.__dict__, "goal": Goal.BUILD_MUSCLE}))
    more, _ = weekly_review(stats(), [0.0, 0.05], 80.0, Goal.BUILD_MUSCLE, t)
    assert (more["kind"], more["delta"]) == ("kcal", 100)
    less, _ = weekly_review(stats(), [0.2, 0.6], 80.0, Goal.BUILD_MUSCLE, t)  # 0.75% a week
    assert (less["kind"], less["delta"]) == ("kcal", -100)
