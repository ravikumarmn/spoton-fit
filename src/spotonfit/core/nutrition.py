"""Nutrition arithmetic. Pure functions, no I/O.

Division of labour:
- The model estimates, per food: how many units (quantity), grams per unit, and the
  nutrients of ONE unit as served (oil/ghee included), plus how oily it is.
- This module does the arithmetic: quantity x per-unit values, meal totals, and a
  consistency check of calories against macros. Changing "6 eggs" to "4 eggs"
  re-scales the numbers without another model call.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# Atwater general factors: energy per gram of macronutrient (kcal/g). These are
# physical constants of nutrition science, not tuning values.
KCAL_PER_G_PROTEIN = 4.0
KCAL_PER_G_CARBS = 4.0
KCAL_PER_G_FAT = 9.0


@dataclass(frozen=True)
class Nutrients:
    kcal: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fibre: float = 0.0

    def __add__(self, o: Nutrients) -> Nutrients:
        return Nutrients(*(getattr(self, f.name) + getattr(o, f.name) for f in fields(self)))

    def scale(self, factor: float) -> Nutrients:
        return Nutrients(*(getattr(self, f.name) * factor for f in fields(self)))

    def rounded(self, ndigits: int = 1) -> Nutrients:
        return Nutrients(*(round(getattr(self, f.name), ndigits) for f in fields(self)))

    def as_dict(self) -> dict[str, float]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def food_key(name: str) -> str:
    """Normalised name for matching a user's remembered foods: lower case, single
    spaces, simple plural removed ("Boiled  Eggs" -> "boiled egg"). Exact match only;
    no fuzzy matching, so one food is never swapped for another."""
    words = name.strip().lower().split()
    if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def item_totals(per_unit: Nutrients, quantity: float) -> Nutrients:
    """Nutrients for `quantity` units (e.g. 6 eggs = 6 x one egg)."""
    return per_unit.scale(quantity).rounded()


def meal_totals(items: list[Nutrients]) -> Nutrients:
    total = Nutrients()
    for n in items:
        total = total + n
    return total.rounded()


def macro_energy(n: Nutrients) -> float:
    """Calories implied by the macros (4 protein + 4 carbs + 9 fat)."""
    return KCAL_PER_G_PROTEIN * n.protein + KCAL_PER_G_CARBS * n.carbs + KCAL_PER_G_FAT * n.fat


def energy_mismatch(n: Nutrients) -> float:
    """Relative gap between stated calories and macro-implied calories (0 = consistent)."""
    implied = macro_energy(n)
    biggest = max(n.kcal, implied)
    return 0.0 if biggest == 0 else abs(n.kcal - implied) / biggest
