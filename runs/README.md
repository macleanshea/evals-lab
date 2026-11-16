# Run log

One row per run. Click a date for the full report. Official scores = code + judge (τ²-bench's rule); code-only shown for reference.

Task sets (see `tasks/fixed_set.json`): runs up to 2026-11-16 00:12 used set v1; the 00:45 run used set v2 (tasks 52, 105, 110 swapped for 88, 20, 2); the 00:56 run is the 74-task train-split sweep; later runs use set v3, 20 tasks where the agent must refuse something. Scores are only comparable within the same task set.

| Date | Prompt | Persona | Tasks x trials | pass^1 | pass^k | pass^1 code-only | pass^k code-only |
|---|---|---|---|---|---|---|---|
| [2026-11-16 00:02](2026-11-16_000222/report.md) | v1 | none | 5 x 1 | 1.00 | 1.00 | 1.00 | 1.00 |
| [2026-11-16 00:12](2026-11-16_001257/report.md) | v1 | none | 20 x 4 | 0.84 | 0.80 | 0.94 | 0.90 |
| [2026-11-16 00:45](2026-11-16_004509/report.md) | v1 | pushback | 20 x 4 | 0.99 | 0.95 | 0.99 | 0.95 |
| [2026-11-16 00:56](2026-11-16_005638/report.md) | v1 | pushback | 74 x 2 | 0.90 | 0.85 | 0.93 | 0.89 |
