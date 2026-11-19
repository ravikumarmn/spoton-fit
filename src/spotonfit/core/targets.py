"""Daily targets and energy expenditure from a user profile. Pure functions, no I/O.

All tuning values (deficit, protein per kg, floors, ...) come from
`config.TargetPolicy` / `config.EnergyPolicy`. The equations below are the published
formulas themselves:
- Mifflin-St Jeor (1990): BMR = 10 x kg + 6.25 x cm - 5 x age + 5 (men) / - 161 (women)
- Katch-McArdle: BMR = 370 + 21.6 x lean body mass (kg)
- MET equation: kcal = MET x body weight (kg) x hours
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from spotonfit.config import EnergyPolicy, TargetPolicy, settings
from spotonfit.core.nutrition import KCAL_PER_G_CARBS, KCAL_PER_G_FAT, KCAL_PER_G_PROTEIN


class Goal(StrEnum):
    LOSE_FAT = "lose_fat"
    BUILD_MUSCLE = "build_muscle"
    MAINTAIN = "maintain"


@dataclass(frozen=True)
class Profile:
    age: int
    sex: str  # "male" | "female"
    height_cm: float
    weight_kg: float
    goal: Goal = Goal.LOSE_FAT
    activity: str = "sedentary"
    body_fat_pct: float | None = None
    goal_weight_kg: float | None = None
    baseline_steps: int = 5000


@dataclass(frozen=True)
class Targets:
    bmi: float
    bmr: float
    maintenance: float
    kcal: int
    kcal_floor: int
    protein_g: int
    fat_g: int
    carbs_g: int
    fibre_g: int
    water_ml: int
    steps: int
    kcal_adjustment: int = 0  # accepted weekly-review changes (cumulative)
    steps_adjustment: int = 0
    maintenance_source: str = "formula"  # formula | learned


def bmi(p: Profile) -> float:
    return p.weight_kg / (p.height_cm / 100) ** 2


def lean_mass(p: Profile) -> float | None:
    return None if p.body_fat_pct is None else p.weight_kg * (1 - p.body_fat_pct / 100)


def bmr(p: Profile) -> float:
    """Katch-McArdle if body fat is known, else Mifflin-St Jeor."""
    lean = lean_mass(p)
    if lean is not None:
        return 370 + 21.6 * lean
    base = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age
    return base + (5 if p.sex == "male" else -161)


def protein_reference_weight(p: Profile, policy: TargetPolicy) -> float:
    """Goal weight, or lean-mass-based weight when body fat is high, so heavy users
    don't get unrealistic protein targets."""
    if p.goal_weight_kg:
        return min(p.weight_kg, p.goal_weight_kg)
    lean = lean_mass(p)
    if lean is not None and p.body_fat_pct > policy.high_body_fat_pct.get(p.sex, math.inf):
        return lean / (1 - policy.reference_body_fat_pct / 100)
    return p.weight_kg


def compute_targets(
    p: Profile,
    week_index: int = 0,
    learned_tdee: float | None = None,
    policy: TargetPolicy | None = None,
    kcal_adjustment: int = 0,
    steps_adjustment: int = 0,
) -> Targets:
    """week_index: weeks since start (drives the step ramp).
    learned_tdee: maintenance learned from the weight trend; overrides the formula.
    kcal_adjustment / steps_adjustment: accepted weekly-review proposals. The calorie
    floor and the step cap still apply after adjustments."""
    policy = policy or settings.targets
    b = bmr(p)
    maintenance = learned_tdee or b * policy.activity_factors.get(p.activity, min(policy.activity_factors.values()))

    floor = max(b, policy.floor_kcal.get(p.sex, max(policy.floor_kcal.values())))
    goal = Goal(p.goal)
    if goal == Goal.LOSE_FAT:
        kcal = max(maintenance * (1 - policy.deficit_fraction), floor)
    elif goal == Goal.BUILD_MUSCLE:
        kcal = maintenance * (1 + policy.surplus_fraction)
    else:
        kcal = maintenance
    kcal = max(kcal + kcal_adjustment, floor)

    protein = policy.protein_g_per_kg[goal.value] * protein_reference_weight(p, policy)
    fat = max(policy.fat_fraction_of_kcal * kcal / KCAL_PER_G_FAT, policy.fat_min_g_per_kg * p.weight_kg)
    carbs = max((kcal - protein * KCAL_PER_G_PROTEIN - fat * KCAL_PER_G_FAT) / KCAL_PER_G_CARBS, policy.carbs_min_g)
    ramp = p.baseline_steps + policy.step_increment_per_week * (week_index + 1)
    steps = min(ramp + steps_adjustment, policy.step_cap)
    step = policy.kcal_round_up_to

    return Targets(
        bmi=round(bmi(p), 1),
        bmr=round(b),
        maintenance=round(maintenance),
        kcal=int(math.ceil(kcal / step) * step),  # round up so we never land under the floor
        kcal_floor=int(round(floor)),
        protein_g=int(round(protein)),
        fat_g=int(round(fat)),
        carbs_g=int(round(carbs)),
        fibre_g=int(round(policy.fibre_g_per_1000_kcal * kcal / 1000)),
        water_ml=int(round(policy.water_ml_per_kg * p.weight_kg, -2)),
        steps=int(round(steps, -2)),
        kcal_adjustment=kcal_adjustment,
        steps_adjustment=steps_adjustment,
        maintenance_source="learned" if learned_tdee else "formula",
    )


# Activity energy -----------------------------------------------------------


def workout_kcal(met: float, minutes: float, weight_kg: float) -> float:
    """MET equation. The MET value for an activity is estimated by the model."""
    return met * weight_kg * minutes / 60


def steps_kcal(steps: int, weight_kg: float, policy: EnergyPolicy | None = None) -> float:
    policy = policy or settings.energy
    return steps / policy.steps_per_km * policy.walk_kcal_per_kg_per_km * weight_kg
