# Run log

One row per run. Click a date for the full report. Official scores = code + judge (τ²-bench's rule); code-only shown for reference.

Task sets (see `tasks/fixed_set.json`): runs up to 2026-11-16 00:12 used set v1; the 00:45 run used set v2 (tasks 52, 105, 110 swapped for 88, 20, 2); the 00:56 run is the 74-task train-split sweep; later runs use set v3, 20 tasks where the agent must refuse something. Scores are only comparable within the same task set.

| Date | Prompt | Persona | Tasks x trials | pass^1 | pass^k | pass^1 code-only | pass^k code-only |
|---|---|---|---|---|---|---|---|
| [2026-11-16 00:02](2026-11-16_000222/report.md) | v1 | none | 5 x 1 | 1.00 | 1.00 | 1.00 | 1.00 |
| [2026-11-16 00:12](2026-11-16_001257/report.md) | v1 | none | 20 x 4 | 0.84 | 0.80 | 0.94 | 0.90 |
| [2026-11-16 00:45](2026-11-16_004509/report.md) | v1 | pushback | 20 x 4 | 0.99 | 0.95 | 0.99 | 0.95 |
| [2026-11-16 00:56](2026-11-16_005638/report.md) | v1 | pushback | 74 x 2 | 0.90 | 0.85 | 0.93 | 0.89 |
| [2026-11-16 01:40](2026-11-16_014008/report.md) | v1 | pushback | 20 x 4 | 0.86 | 0.70 | 0.86 | 0.70 |
| [2026-11-16 02:53](2026-11-16_025323/report.md) | v2 | pushback | 20 x 4 | 0.90 | 0.70 | 0.91 | 0.70 |

## Inspect runs (τ²-bench airline, `inspect_evals/tau2_airline`)

Logs in `inspect/logs/` are slimmed copies (the airline database snapshots removed; see `inspect/slim_log.py`). Different domain and grader from the table above (airline, code-only grading: database + required facts, no LLM judge; see `inspect/NOTES.md`), so not comparable to it. Agent Haiku 5.5, customer simulator Sonnet 5.5. Viewer: `inspect/logs-www/` (served by Vercel once set up).

| Date | Tasks (airline ids) | Tasks x epochs | pass^1 | pass^k | Tokens (agent / simulator) | Cost | Log |
|---|---|---|---|---|---|---|---|
| [2026-11-16 16:29](../inspect/reports/2026-11-16T16-29-43_tau2-airline_5x1.txt) | 0,1,3,4,5 | 5 x 1 | 0.80 | – | 332k / 40k | $0.07 | [.eval](../inspect/logs/2026-11-16T16-29-43-00-00_tau2-airline_hxZoWMmxJjwFTmr2kxJ95v.eval) |
| [2026-11-16 16:48](../inspect/reports/2026-11-16T16-48-39_tau2-airline_20x4.txt) ([analysis](../inspect/reports/2026-11-16T16-48-39_tau2-airline_20x4_analysis.md)) | first 20 of the train split: 0,1,3,4,5,7,9,10,11,12,14,15,17,20,21,23,27,28,33,34 | 20 x 4 | 0.64 | 0.55 | 7.31M / 0.75M | $1.27 | [.eval](../inspect/logs/2026-11-16T16-48-39-00-00_tau2-airline_RCuQu5GYUMrKiPcEVyBNAQ.eval) |
| [2026-11-16 21:37](../inspect/reports/2026-11-16T21-37-52_tau2-airline-custom_v0_10x4.txt) | custom task, prompt v0 (= port's prompt); rest of the train split: 36,38,39,40,41,42,43,46,47,49 | 10 x 4 | 0.78 | 0.70 | 2.82M / 0.27M | $0.44 + $0.36 judge | [.eval](../inspect/logs/2026-11-16T21-37-52-00-00_tau2-airline-custom_LNWGLHaS9AXPhFwfmnHBcK.eval) |
| [2026-11-16 21:45](../inspect/reports/2026-11-16T21-45-28_tau2-airline-custom_v1_30x4.txt) ([vs v0](../inspect/reports/2026-11-16_train_v0_vs_v1.txt)) | custom task, **prompt v1**; full train split (30) | 30 x 4 | 0.72 | 0.70 | 10.51M / 1.16M | $2.19 + $1.48 judge | [.eval](../inspect/logs/2026-11-16T21-45-28-00-00_tau2-airline-custom_MZrsGr8ah884Z6HjrEPaWE.eval) |
| [2026-11-17 01:27](../inspect/reports/2026-11-17T01-27-53_test_v0_20x4.txt) | **TEST split**, prompt v0 (= port's prompt): 2,6,8,13,16,18,19,22,24,25,26,29,30,31,32,35,37,44,45,48 | 20 x 4 | 0.64 | 0.55 | 7.27M / 0.69M | $1.07 + $0.95 judge | [.eval](../inspect/logs/2026-11-17T01-27-53-00-00_tau2-airline-custom_WV8WcevgpyL2AXXtYmvQWb.eval) |
| [2026-11-17 01:40](../inspect/reports/2026-11-17T01-40-54_test_v1_20x4.txt) ([vs v0](../inspect/reports/2026-11-17_test_v0_vs_v1.txt)) | **TEST split**, prompt v1 (same samples) | 20 x 4 | 0.68 | 0.60 | 7.21M / 0.70M | $1.07 + $0.95 judge | [.eval](../inspect/logs/2026-11-17T01-40-54-00-00_tau2-airline-custom_j75wFjybYzxMPdoDUpP55B.eval) |
