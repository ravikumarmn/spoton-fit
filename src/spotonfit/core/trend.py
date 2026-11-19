"""Weight trend, learned maintenance (TDEE), predictions and history aggregation.

Pure functions (pandas, no database). Parameters come from `config.EnergyPolicy`.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from spotonfit.config import EnergyPolicy, settings

HISTORY_COLUMNS = ["kcal", "protein", "carbs", "fat", "water_ml", "steps"]


def period_freq(period: str) -> str:
    """pandas resample code; weekly buckets end on the day before WEEK_STARTS_ON."""
    if period == "week":
        return "W-SAT" if settings.week_starts_on == "sunday" else "W-SUN"
    return {"month": "MS", "year": "YS"}[period]


def weight_trend(weights: list[tuple[dt.date, float]], alpha: float | None = None) -> list[tuple[dt.date, float]]:
    """Exponential moving average over weigh-ins, so water swings don't distort the trend."""
    alpha = settings.energy.trend_alpha if alpha is None else alpha
    trend: list[tuple[dt.date, float]] = []
    t = None
    for day, kg in sorted(weights):
        t = kg if t is None else t + alpha * (kg - t)
        trend.append((day, round(t, 2)))
    return trend


def estimate_tdee(avg_intake: float, trend_change_kg: float, days: int, policy: EnergyPolicy | None = None) -> float:
    """TDEE = average intake - (trend change x energy per kg / days)."""
    policy = policy or settings.energy
    return avg_intake - trend_change_kg * policy.kcal_per_kg_body_weight / days


def observed_tdee(
    df: pd.DataFrame, policy: EnergyPolicy | None = None, full_trend: list[tuple[dt.date, float]] | None = None
) -> dict | None:
    """What the data says maintenance is, from a daily frame (services.ledger.daily_frame):
    {"tdee", "avg_intake", "trend_change_kg", "days", "logged_days"}, or None when there
    aren't enough logged days or weigh-ins yet (TDEE_MIN_LOGGED_DAYS / TDEE_MIN_WEIGH_INS).

    full_trend: the trend over ALL weigh-ins (not just this window). Pass it when available:
    an EMA started at the window's first weigh-in lags behind the real slope and
    under-states the change (and so the maintenance). Without it, the window is used."""
    policy = policy or settings.energy
    if df.empty or df["logged"].sum() < policy.tdee_min_logged_days:
        return None
    weights = [(r.day, r.weight_kg) for r in df.itertuples() if pd.notna(r.weight_kg)]
    if len(weights) < policy.tdee_min_weigh_ins:
        return None
    window = set(df["day"])
    trend = [(d, t) for d, t in full_trend if d in window] if full_trend else []
    if len(trend) < 2:
        trend = weight_trend(weights, policy.trend_alpha)
    days = (trend[-1][0] - trend[0][0]).days or 1
    avg_intake = float(df.loc[df["logged"], "kcal"].mean())
    change = trend[-1][1] - trend[0][1]
    return {
        "tdee": estimate_tdee(avg_intake, change, days, policy),
        "avg_intake": avg_intake,
        "trend_change_kg": round(change, 2),
        "days": days,
        "logged_days": int(df["logged"].sum()),
    }


def blend(prior: float, observed: float, policy: EnergyPolicy | None = None) -> float:
    """prior x w + observed x (1 - w): one week's evidence moves the estimate only part way."""
    w = (policy or settings.energy).tdee_prior_weight
    return w * prior + (1 - w) * observed


def gradual(previous: float, candidate: float, policy: EnergyPolicy | None = None) -> float:
    """Cap the weekly change of the learned maintenance (TDEE_MAX_WEEKLY_CHANGE_KCAL)."""
    cap = (policy or settings.energy).tdee_max_weekly_change_kcal
    return previous + max(-cap, min(cap, candidate - previous))


def learned_tdee_from_frame(df: pd.DataFrame, prior: float, policy: EnergyPolicy | None = None) -> float | None:
    """Blended learned maintenance (no weekly cap), or None when there isn't enough data."""
    obs = observed_tdee(df, policy)
    return None if obs is None else round(blend(prior, obs["tdee"], policy))


def predict_weight(
    trend_kg: float, tdee: float, planned_kcal: float, days: int, policy: EnergyPolicy | None = None
) -> tuple[float, float]:
    """Range for trend weight after `days`, given the TDEE uncertainty band. Always a range."""
    policy = policy or settings.energy

    def at(t: float) -> float:
        return trend_kg - (t - planned_kcal) * days / policy.kcal_per_kg_body_weight

    band = policy.prediction_band_kcal
    return round(at(tdee + band), 1), round(at(tdee - band), 1)


def aggregate(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """period: day | week | month | year. Averages over days that were logged."""
    if df.empty or period == "day":
        return df
    d = df.copy()
    d["day"] = pd.to_datetime(d["day"])
    logged = d[d["logged"]].set_index("day")
    freq = period_freq(period)
    grouped = logged.resample(freq)[HISTORY_COLUMNS].mean().round(0)
    grouped["days_logged"] = logged.resample(freq)["logged"].sum()
    grouped["avg_weight_kg"] = d.set_index("day")["weight_kg"].resample(freq).mean().round(1)
    return grouped.reset_index().rename(columns={"day": period})
