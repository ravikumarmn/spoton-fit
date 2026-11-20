"""Structured outputs the models must return (validated by Pydantic).

Field descriptions are sent to the model as part of the JSON schema, so they double
as instructions. The model estimates; code multiplies and adds (core/nutrition.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MealSlot = Literal["breakfast", "snack", "lunch", "pre_workout", "dinner", "bedtime"]
OilLevel = Literal["none", "light", "medium", "heavy"]


class NutrientsPerUnit(BaseModel):
    """Nutrients of ONE unit of the food exactly as served."""

    kcal: float = Field(ge=0, description="Calories of one unit, including any cooking oil, ghee or butter")
    protein: float = Field(ge=0, description="Protein grams in one unit")
    carbs: float = Field(ge=0, description="Carbohydrate grams in one unit")
    fat: float = Field(ge=0, description="Fat grams in one unit, including cooking oil, ghee or butter")
    fibre: float = Field(0, ge=0, description="Fibre grams in one unit")


class FoodItemEstimate(BaseModel):
    name: str = Field(description="Common food name, e.g. 'boiled egg', 'chicken curry', 'idli'")
    quantity: float = Field(gt=0, description="How many units: count every piece you see, e.g. 6 for six eggs")
    unit: str = Field(description="piece, katori (~150 g), cup, plate, glass, tbsp, tsp, slice, serving")
    grams_per_unit: float = Field(gt=0, description="Estimated edible grams of ONE unit")
    per_unit: NutrientsPerUnit
    oil_level: OilLevel = Field(description="Visible or likely added oil/ghee/butter in this food")
    remark: str | None = Field(
        default=None,
        description="One short note for the user when useful, e.g. 'deep-fried, very oily' or 'cream-based gravy'",
    )
    confidence: float = Field(ge=0, le=1, description="How sure you are about the food AND the portion")


class MealEstimate(BaseModel):
    items: list[FoodItemEstimate]
    meal_slot: MealSlot
    clarify: str | None = Field(
        default=None,
        description="At most one short question, only if a calorie-dense item is very uncertain",
    )


class SuggestionOption(BaseModel):
    title: str = Field(description="Short name, e.g. 'Egg bhurji with 2 chapatis'")
    items: list[FoodItemEstimate] = Field(min_length=1, max_length=4)
    why: str = Field(description="One sentence: why this fits the user's remaining calories and protein")


class MealSuggestions(BaseModel):
    options: list[SuggestionOption] = Field(min_length=1, max_length=3)


class SafetyCheck(BaseModel):
    """Whether a matched red-flag phrase is something the user reports experiencing."""

    applies: bool = Field(
        description="True if the user says they have or recently had this symptom (or you are unsure); "
        "false only if it is clearly negated, hypothetical, about someone else, or a general question"
    )


class RuleSpec(BaseModel):
    """A plain-English food rule turned into fields the rule engine can check."""

    understood: bool = Field(description="False if the text is not a food/drink rule this app can check")
    kind: Literal["max_days_per_week", "max_per_day", "not_after", "not_before", "avoid"] = Field(
        description=(
            "max_days_per_week: on at most N days per week; max_per_day: at most N servings per day; "
            "not_after / not_before: a time limit; avoid: never"
        )
    )
    food: str = Field(description="The food or drink, singular and simple, e.g. 'idli', 'tea', 'sugar', 'biryani'")
    limit: int | None = Field(None, ge=0, le=50, description="N for max_days_per_week or max_per_day, else null")
    time: str | None = Field(None, description="24-hour HH:MM local time for not_after / not_before, else null")
    summary: str = Field(description="The rule restated in one short, friendly sentence for the user to confirm")


class WorkoutItem(BaseModel):
    activity: str = Field(description="e.g. 'cycling', 'treadmill walk', 'weight training', 'badminton'")
    minutes: float | None = Field(description="Duration in minutes; null if the user did not say")
    intensity: Literal["light", "moderate", "vigorous"] = Field(description="Effort implied by the text")
    met: float = Field(
        gt=0, le=25, description="Metabolic equivalent (MET) for this activity at this intensity, per the Compendium"
    )


class WorkoutLog(BaseModel):
    workouts: list[WorkoutItem]
