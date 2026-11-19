"""Food-logging evals. Runs labelled meals through the food graph, compares the
estimated calories/protein with ground truth, and logs metrics + per-case results
to MLflow.

Usage (from the repo root):
  uv run python evals/run_evals.py           # live Gemini (needs GOOGLE_API_KEY in env or .env)
  uv run python evals/run_evals.py --stub    # offline pipeline check, no API calls (used in CI)
  uv run --group evals python evals/run_evals.py   # also log the run to MLflow

Env: MLFLOW_TRACKING_URI (default sqlite:///mlflow.db), EVAL_MAX_KCAL_MAPE (default 25)

Data (evals/data/*.jsonl), one case per line:
  {"text": "...", "truth_kcal": 429, "truth_protein_g": 37.8, "truth_source": "..."}
The current truth values come from the old v0.2 seed table and are APPROXIMATE.
Replace them with weighed meals (kitchen scale + IFCT/label values) to make the
live MAPE meaningful. --stub feeds the truth back in, so it checks plumbing only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # works without `uv sync` installing the package

from spotonfit.agents.food_logger import build_food_graph  # noqa: E402
from spotonfit.agents.schemas import FoodItemEstimate, MealEstimate, NutrientsPerUnit  # noqa: E402
from spotonfit.config import settings  # noqa: E402


def stub_extractor_for(case: dict):
    """Returns the truth as a single item, to exercise the pipeline offline."""

    async def _extract(_state):
        per_unit = NutrientsPerUnit(kcal=case["truth_kcal"], protein=case["truth_protein_g"], carbs=0, fat=0)
        item = FoodItemEstimate(
            name=case["text"], quantity=1, unit="serving", grams_per_unit=1, per_unit=per_unit, oil_level="none",
            confidence=1,
        )  # fmt: skip
        return MealEstimate(meal_slot="lunch", items=[item])

    return _extract


async def run_cases(cases: list[dict], stub: bool) -> list[dict]:
    rows = []
    graph = None if stub else build_food_graph()
    for case in cases:
        g = build_food_graph(stub_extractor_for(case)) if stub else graph
        out = await g.ainvoke({"note": case["text"], "local_time": "13:30"})
        kcal, protein = out["totals"]["kcal"], out["totals"]["protein"]
        rows.append(
            {
                "text": case["text"],
                "pred_kcal": round(kcal),
                "true_kcal": case["truth_kcal"],
                "kcal_ape": round(abs(kcal - case["truth_kcal"]) / case["truth_kcal"] * 100, 1),
                "pred_protein_g": round(protein, 1),
                "true_protein_g": case["truth_protein_g"],
                "protein_ape": round(abs(protein - case["truth_protein_g"]) / max(case["truth_protein_g"], 1) * 100, 1),
                "items": [(i["name"], i["quantity"]) for i in out["items"]],
                "oily_items": out.get("oily_items", []),
                "warnings": out.get("warnings", []),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stub", action="store_true")
    ap.add_argument("--data", default=str(ROOT / "evals/data/text_meals.jsonl"))
    args = ap.parse_args()

    if not args.stub and not settings.has_llm_key:
        print("GOOGLE_API_KEY not set (env or .env); skipping live evals.")
        return 0

    with open(args.data, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    rows = asyncio.run(run_cases(cases, args.stub))

    kcal_mape = sum(r["kcal_ape"] for r in rows) / len(rows)
    prot_mape = sum(r["protein_ape"] for r in rows) / len(rows)
    summary = {
        "cases": len(rows),
        "kcal_mape": round(kcal_mape, 1),
        "protein_mape": round(prot_mape, 1),
        "mode": "stub" if args.stub else "live",
        "vision_model": settings.vision_model,
    }
    print(json.dumps(summary, indent=2))
    if not args.stub:
        for r in rows:
            print(f"  {r['kcal_ape']:5.1f}%  {r['pred_kcal']:5d} vs {r['true_kcal']:5d} kcal  {r['text']}")
    Path("eval_results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    try:
        import mlflow

        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
        mlflow.set_experiment("spotonfit-evals")
        with mlflow.start_run(run_name=f"food-{summary['mode']}"):
            mlflow.log_params(
                {
                    "mode": summary["mode"],
                    "cases": len(rows),
                    "vision_model": settings.vision_model,
                    "vision_thinking": settings.vision_thinking,
                }
            )
            mlflow.log_metrics({"kcal_mape": kcal_mape, "protein_mape": prot_mape})
            mlflow.log_dict({"rows": rows}, "results.json")
    except ImportError:
        print("mlflow not installed; skipped MLflow logging")

    limit = float(os.environ.get("EVAL_MAX_KCAL_MAPE", "25"))
    if kcal_mape > limit:
        print(f"FAIL: kcal MAPE {kcal_mape:.1f}% > {limit}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
