# Weighed meal eval set

The current `evals/data/text_meals.jsonl` truth values come from an old seed table and are **approximate**.
To measure how accurate SpotOn really is, build a set of meals you weighed yourself. With 20 or more meals,
the live run's MAPE (mean absolute percentage error) is a number you can quote.

## 1. Weigh and record (about 5 minutes per meal)

For each meal you eat at home:

1. Put the plate on a kitchen scale and note the **cooked weight of each food** in grams.
2. Note the **oil, ghee, butter and sugar** you added (teaspoons or grams). These matter most.
3. Look up calories and protein per 100 g:
   - **IFCT 2017** (Indian Food Composition Tables, NIN) for home foods: rice, dal, roti, sabzi, eggs, milk.
   - The **pack label** for anything packaged.
   - For cooked dishes, add up the raw ingredients and divide by the cooked weight.
4. Work out the truth: grams ÷ 100 × value per 100 g, for each food, then add them up.
5. Write the meal the way you'd type it in the app, for example "2 rotis, 1 katori dal, half katori bhindi".

## 2. Add one line per meal

Create `evals/data/weighed_meals.jsonl` (one JSON object per line):

```json
{"text": "<what you'd type in the app>", "truth_kcal": <number>, "truth_protein_g": <number>, "truth_items": [["<food>", <grams>], ["<food>", <grams>]], "truth_source": "weighed <date>, IFCT 2017 / label"}
```

Only real, weighed numbers. Don't copy values from the app's own estimates.

## 3. Run it

```bash
uv run python evals/run_evals.py --data evals/data/weighed_meals.jsonl          # live Gemini
uv run --group evals python evals/run_evals.py --data evals/data/weighed_meals.jsonl   # also log to MLflow
```

The run prints kcal and protein MAPE and writes per-meal results to `eval_results.json`. Look at the worst
meals: portion size (count, grams) is usually the error, not the food.

## Limits

- The runner is text-only for now. Photo meals need a `photo` field and a runner change (not built).
- 20 meals from one kitchen is a start, not a benchmark. Say so when you publish the number.
