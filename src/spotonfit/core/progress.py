"""Progress intelligence (PRD P-03..P-05). Pure functions, no I/O.

- `goal_eta`: when the goal weight is likely, as a date RANGE (never a promise), from the
  trend weight, maintenance +- its uncertainty band, and the planned calorie target.
- `week_stats` / `weekly_review`: a week's averages, adherence and trend, plus at most one
  proposed target change, following the PRD's rules:
    * losing faster than ~1% of body weight a week -> eat a little more (safety first)
    * progress stalled for STALL_WEEKS with consistent logging -> +steps, else -kcal
      (never below the floor)
    * inconsistent logging -> no change; focus on logging
All thresholds come from config.ReviewPolicy / EnergyPolicy.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import pandas as pd

from spotonfit.config import EnergyPolicy, ReviewPolicy, TargetPolicy, settings
from spotonfit.core.targets import Goal, Targets


def date_phrase(d: dt.date) -> str:
    """12 Jan 2027 -> 'mid-Jan 2027' (ranges read better than exact days)."""
    part = "early" if d.day <= 10 else "mid" if d.day <= 20 else "late"
    return f"{part}-{d:%b %Y}"


def goal_eta(
    trend_kg: float,
    goal_kg: float,
    maintenance: float,
    planned_kcal: float,
    today: dt.date,
    policy: EnergyPolicy | None = None,
) -> dict:
    """Likely date range for reaching goal_kg at the planned intake."""
    policy = policy or settings.energy
    distance = goal_kg - trend_kg
    if abs(distance) < 0.1:
        return {
            "on_track": True,
            "earliest": None,
            "latest": None,
            "message": f"You're at your goal of {goal_kg:g} kg.",
        }
    band, kpk = policy.prediction_band_kcal, policy.kcal_per_kg_body_weight
    # daily energy balance range (positive = surplus) given the maintenance uncertainty
    balances = (planned_kcal - (maintenance + band), planned_kcal - (maintenance - band))
    wanted = [b for b in balances if (b < 0) == (distance < 0) and b != 0]
    if len(wanted) == 0:
        direction = "lose" if distance < 0 else "gain"
        return {
            "on_track": False,
            "earliest": None,
            "latest": None,
            "message": f"At your current target you're not likely to {direction} toward {goal_kg:g} kg; "
            "the weekly review will suggest a change if this continues.",
        }
    fast = max(abs(b) for b in wanted) / kpk  # kg per day
    slow = min(abs(b) for b in wanted) / kpk if len(wanted) == 2 else None
    earliest = today + dt.timedelta(days=math.ceil(abs(distance) / fast))
    latest = today + dt.timedelta(days=math.ceil(abs(distance) / slow)) if slow else None
    if latest:
        msg = f"{goal_kg:g} kg likely between {date_phrase(earliest)} and {date_phrase(latest)}."
    else:
        msg = f"{goal_kg:g} kg possible from {date_phrase(earliest)}; the later end is too uncertain to call."
    return {"on_track": True, "earliest": earliest, "latest": latest, "message": msg + " A range, not a promise."}


@dataclass(frozen=True)
class WeekStats:
    days_logged: int
    avg_kcal: float | None
    avg_protein: float | None
    avg_steps: float | None
    on_target_days: int
    protein_hit_days: int


def week_stats(week: pd.DataFrame, targets: Targets, policy: ReviewPolicy | None = None) -> WeekStats:
    """Averages over logged days (week = 7 rows of services.ledger.daily_frame)."""
    policy = policy or settings.reviews
    logged = week[week["logged"]]
    tol = policy.kcal_on_target_tolerance
    on_target = logged[(logged["kcal"] - targets.kcal).abs() <= tol * targets.kcal]
    protein_hit = logged[logged["protein"] >= policy.protein_hit_fraction * targets.protein_g]
    steps = week[week["steps"] > 0]["steps"]
    return WeekStats(
        days_logged=len(logged),
        avg_kcal=round(float(logged["kcal"].mean())) if len(logged) else None,
        avg_protein=round(float(logged["protein"].mean())) if len(logged) else None,
        avg_steps=round(float(steps.mean())) if len(steps) else None,
        on_target_days=len(on_target),
        protein_hit_days=len(protein_hit),
    )


def weekly_review(
    stats: WeekStats,
    weekly_trend_changes: list[float],
    trend_kg: float | None,
    goal: Goal,
    targets: Targets,
    review: ReviewPolicy | None = None,
    target_policy: TargetPolicy | None = None,
) -> tuple[dict | None, list[str]]:
    """(proposal or None, notes). weekly_trend_changes: kg per week, oldest first, ending
    with the reviewed week."""
    review = review or settings.reviews
    target_policy = target_policy or settings.targets
    notes: list[str] = []
    consistent = stats.days_logged >= review.good_adherence_days and stats.on_target_days >= review.good_adherence_days
    last = weekly_trend_changes[-1] if weekly_trend_changes else None
    recent = weekly_trend_changes[-review.stall_weeks :]
    enough_weeks = len(recent) == review.stall_weeks
    pct = (100 * last / trend_kg) if (last is not None and trend_kg) else None

    def kcal(delta: int, reason: str) -> dict:
        new = targets.kcal + delta
        verb = "Add" if delta > 0 else "Cut"
        return {
            "kind": "kcal",
            "delta": delta,
            "text": f"{verb} {abs(delta)} kcal a day (to about {new:,})",
            "reason": reason,
        }

    if stats.days_logged < review.good_adherence_days:
        notes.append(
            f"You logged {stats.days_logged} of 7 days. "
            f"Aim for {review.good_adherence_days}+ so the numbers are reliable;"
            " no target change this week."
        )
        return None, notes

    if goal == Goal.LOSE_FAT:
        if pct is not None and -pct > review.max_weekly_loss_pct:
            notes.append(
                f"Your trend fell {abs(last):.1f} kg this week (over {review.max_weekly_loss_pct:g}% of body weight)."
            )
            return kcal(
                +review.proposal_kcal, "You're losing faster than is healthy to sustain; eat a little more."
            ), notes
        stalled = enough_weeks and all(c > -review.stall_kg_per_week for c in recent)
        if stalled and consistent:
            if targets.steps + review.proposal_steps <= target_policy.step_cap:
                new_steps = targets.steps + review.proposal_steps
                return {
                    "kind": "steps",
                    "delta": review.proposal_steps,
                    "text": f"Add {review.proposal_steps:,} steps a day (to {new_steps:,})",
                    "reason": (
                        f"Your trend hasn't moved for {review.stall_weeks} weeks even though you've been consistent."
                    ),
                }, notes
            if targets.kcal - review.proposal_kcal >= targets.kcal_floor:
                return kcal(
                    -review.proposal_kcal, "Your trend hasn't moved and your steps are already at the cap."
                ), notes
            notes.append("You're at the calorie floor and the step cap; keep going, and check your logging accuracy.")
        elif stalled:
            notes.append(
                "Progress is slow, but logging wasn't consistent enough to change targets. Focus on consistency."
            )
    elif goal == Goal.BUILD_MUSCLE:
        if pct is not None and pct > review.max_weekly_gain_pct:
            return kcal(-review.proposal_kcal, "You're gaining faster than lean gain allows; trim a little."), notes
        if enough_weeks and consistent and all(c < review.stall_kg_per_week for c in recent):
            return kcal(+review.proposal_kcal, f"Your weight hasn't gone up for {review.stall_weeks} weeks."), notes
    else:
        drift = review.maintain_drift_kg_per_week
        if enough_weeks and consistent and all(c < -drift for c in recent):
            return kcal(+review.proposal_kcal, "Your weight is drifting down."), notes
        if enough_weeks and consistent and all(c > drift for c in recent):
            return kcal(-review.proposal_kcal, "Your weight is drifting up."), notes
    if not notes:
        if enough_weeks:
            notes.append("On track. Keep your targets as they are.")
        else:
            notes.append(f"Too early to judge your trend; that needs {review.stall_weeks} weeks of weigh-ins.")
    return None, notes
