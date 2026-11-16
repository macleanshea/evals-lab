# Run 2026-11-16_000222

Agent `claude-haiku-5-5` with `prompts/agent_v1.md`; customer simulator `claude-sonnet-5-5`; judge `claude-sonnet-5-5`; persona: (empty)

## Summary

| Grading | Tasks x trials | pass^1 | pass^k (k=1) |
|---|---|---|---|
| Code only | 5 x 1 | 1.00 | 1.00 |
| Code + judge (official) | 5 x 1 | 1.00 | 1.00 |

Prompt `v1`. Total tokens: 505,721. Judge-graded tasks: 19, 3, 46.

**Code only** = the conversation ended normally and the database matches. **Code + judge** additionally requires the LLM judge to accept every written check; this is τ²-bench's own pass rule. They differ only on judge-graded tasks.

## Per-task results

Each cell: code-only / code + judge. Click for the transcript.

| Task | Judge-graded | Trial 1 | Reason (first trial failing the official verdict) |
|---|---|---|---|
| 19 | yes | [PASS / PASS](task-19_trial-1.md) |  |
| 3 | yes | [PASS / PASS](task-3_trial-1.md) |  |
| 52 | no | [PASS / PASS](task-52_trial-1.md) |  |
| 46 | yes | [PASS / PASS](task-46_trial-1.md) |  |
| 41 | no | [PASS / PASS](task-41_trial-1.md) |  |

## Tokens

| Role | Input | Output |
|---|---|---|
| user_sim | 43,372 | 2,529 |
| agent | 432,382 | 11,647 |
| judge | 15,247 | 544 |
| **total** | | **505,721** |
