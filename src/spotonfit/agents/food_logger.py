"""Food logging as an async LangGraph graph:

    extract  (model: photo and/or text -> MealEstimate: foods, counts, per-unit nutrients, oil)
      -> compute  (code: quantity x per-unit nutrients, meal totals)
      -> validate (code: calories vs macros, low confidence, oily items -> warnings)

There is no food table: the model estimates what ONE unit of each food contains (a
"right-ballpark" estimate, not a lab value) and code does all the arithmetic. Every
item is shown to the user for review before anything is saved.

Personal food memory: `state["memory"]` holds the user's own per-unit values for foods
they corrected before (keyed by core.nutrition.food_key). When the model names one of
those foods, the user's values replace the estimate (source "memory").
"""

from __future__ import annotations

import base64
import io
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from spotonfit.agents.schemas import FoodItemEstimate, MealEstimate
from spotonfit.config import settings
from spotonfit.core.nutrition import Nutrients, energy_mismatch, food_key, item_totals, meal_totals

log = logging.getLogger(__name__)

SYSTEM = """You are a nutrition estimator for a calorie-tracking app used mainly in India.
From the photo and/or the user's note, list every food and drink and estimate its nutrition.

How to estimate:
- COUNT carefully: quantity is the number of units (6 eggs -> quantity 6, unit "piece").
- per_unit is for ONE unit as served. The app multiplies by quantity; do not pre-multiply.
- Include cooking oil, ghee, butter, cream and sugar in per_unit (fried and restaurant food carry a lot).
- Set oil_level from visible shine, frying, gravy oil or tadka. If a food is fried or very oily,
  say so in remark (e.g. "deep-fried, very oily").
- Use Indian household units where natural (piece, katori ~150 g, ladle, cup, plate, glass).
- If the user's note gives counts or amounts, the note wins over the photo.
- Be realistic, not optimistic: photo estimates usually miss hidden fat, so do not under-count oil.
- Ask at most one clarify question, only for a calorie-dense item you are unsure about.
- Choose meal_slot from the local time given."""


class FoodState(TypedDict, total=False):
    image_b64: str | None
    mime: str
    note: str | None
    local_time: str
    memory: dict[str, dict]  # food_key -> {"name", "unit", "grams_per_unit", "per_unit": {...}}
    estimate: MealEstimate
    items: list[dict]
    totals: dict
    oily_items: list[str]
    warnings: list[str]
    latency_ms: int


Extractor = Callable[[FoodState], Awaitable[MealEstimate]]


def shrink_image(data: bytes, max_side: int | None = None) -> tuple[str, str]:
    """Resize to <= max_side px JPEG and drop all metadata (EXIF incl. GPS is not copied).

    Returns (base64, mime). CPU-bound: call via `asyncio.to_thread` from async code.
    Raises PIL.UnidentifiedImageError / OSError for undecodable data.
    """
    from PIL import Image, ImageOps

    side = max_side or settings.image_max_side_px
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")  # keep phone photos upright
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=settings.image_jpeg_quality)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def build_prompt(state: FoodState) -> list:
    """System + user messages. Text goes before the image, as Google's
    image-understanding guide recommends for a single image."""
    text = f"Local time: {state.get('local_time', '')}. User note: {state.get('note') or '(none)'}"
    known = [m["name"] for m in list((state.get("memory") or {}).values())[: settings.food_memory_prompt_limit]]
    if known:
        text += "\nFoods this user logs (use these exact names when they match): " + ", ".join(known)
    content: list[dict] = [{"type": "text", "text": text}]
    if state.get("image_b64"):
        # LangChain standard multimodal block; langchain-google-genai maps it to inline_data.
        content.append({"type": "image", "base64": state["image_b64"], "mime_type": state.get("mime", "image/jpeg")})
    return [SystemMessage(SYSTEM), HumanMessage(content=content)]


def gemini_extractor(model=None) -> Extractor:
    async def _extract(state: FoodState) -> MealEstimate:
        from spotonfit.agents.models import vision_model

        llm = (model or vision_model()).with_structured_output(MealEstimate)
        return await llm.ainvoke(build_prompt(state))

    return _extract


def per_unit_nutrients(it: FoodItemEstimate) -> Nutrients:
    return Nutrients(**it.per_unit.model_dump())


def item_row(it: FoodItemEstimate, remembered: dict | None = None) -> dict:
    """One draft item: per-unit values (the user's remembered ones if any, else the
    model's estimate) plus code-computed totals."""
    if remembered:
        per_unit = Nutrients(**remembered["per_unit"])
        grams_per_unit = remembered.get("grams_per_unit") or it.grams_per_unit
        name, unit, source = remembered["name"], remembered["unit"], "memory"
    else:
        per_unit, grams_per_unit = per_unit_nutrients(it), it.grams_per_unit
        name, unit, source = it.name, it.unit, "ai_estimate"
    totals = item_totals(per_unit, it.quantity)
    return {
        "name": name,
        "quantity": it.quantity,
        "unit": unit,
        "grams_per_unit": round(grams_per_unit),
        "grams": round(grams_per_unit * it.quantity),
        "per_unit": per_unit.rounded().as_dict(),
        **totals.as_dict(),
        "oil_level": it.oil_level,
        "remark": it.remark,
        "confidence": it.confidence,
        "source": source,
    }


async def compute(state: FoodState) -> FoodState:
    memory = state.get("memory") or {}
    items = [item_row(it, memory.get(food_key(it.name))) for it in state["estimate"].items]
    totals = meal_totals([Nutrients(*(i[k] for k in ("kcal", "protein", "carbs", "fat", "fibre"))) for i in items])
    return {"items": items, "totals": totals.as_dict()}


async def validate(state: FoodState) -> FoodState:
    """Sanity checks on the model's numbers. Nothing is changed; problems become warnings."""
    policy = settings.estimates
    warnings: list[str] = []
    oily: list[str] = []
    if not state["items"]:
        warnings.append("No food was recognised. Try a clearer photo or describe the meal.")
    remembered = {food_key(k) for k in (state.get("memory") or {})}
    for it in state["estimate"].items:
        if food_key(it.name) in remembered:  # the user's own confirmed values
            if it.oil_level in policy.oily_levels:
                oily.append(it.name)
            continue
        if energy_mismatch(per_unit_nutrients(it)) > policy.macro_energy_tolerance:
            warnings.append(f"{it.name}: calories don't add up with protein/carbs/fat; please check this item.")
        if it.confidence < policy.low_confidence:
            warnings.append(f"{it.name}: not sure about this one; check the food and amount.")
        if it.oil_level in policy.oily_levels:
            oily.append(it.name)
    return {"warnings": warnings, "oily_items": oily}


def build_food_graph(extractor: Extractor | None = None):
    """Compile the graph. Pass a stub `extractor` (async) for tests and offline evals."""
    extract_fn = extractor or gemini_extractor()

    async def extract(state: FoodState) -> FoodState:
        t0 = time.perf_counter()
        est = await extract_fn(state)
        ms = int((time.perf_counter() - t0) * 1000)
        log.info("food extract: %d items in %d ms", len(est.items), ms)
        return {"estimate": est, "latency_ms": ms}

    g = StateGraph(FoodState)
    g.add_node("extract", extract)
    g.add_node("compute", compute)
    g.add_node("validate", validate)
    g.add_edge(START, "extract")
    g.add_edge("extract", "compute")
    g.add_edge("compute", "validate")
    g.add_edge("validate", END)
    return g.compile(name="food_logger")


async def estimate_text(graph, text: str, local_time: str = "", memory: dict | None = None) -> dict:
    """Run the graph on a text description (used by the coach's tools)."""
    out = await graph.ainvoke({"note": text, "local_time": local_time, "memory": memory or {}})
    return {"items": out["items"], "totals": out["totals"], "warnings": out.get("warnings", [])}
