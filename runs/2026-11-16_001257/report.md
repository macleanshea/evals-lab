# Run 2026-11-16_001257

Agent `claude-haiku-5-5` with `prompts/agent_v1.md`; customer simulator `claude-sonnet-5-5`; judge `claude-sonnet-5-5`; persona: (empty)

## Summary

| Grading | Tasks x trials | pass^1 | pass^k (k=4) |
|---|---|---|---|
| Code only | 20 x 4 | 0.94 | 0.90 |
| Code + judge (official) | 20 x 4 | 0.84 | 0.80 |

Prompt `v1`. Total tokens: 8,266,340. Judge-graded tasks: 19, 3, 46, 16, 4, 105, 113, 47, 110.

**Code only** = the conversation ended normally and the database matches. **Code + judge** additionally requires the LLM judge to accept every written check; this is τ²-bench's own pass rule. They differ only on judge-graded tasks.

## Per-task results

Each cell: code-only / code + judge. Click for the transcript.

| Task | Judge-graded | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Reason (first trial failing the official verdict) |
|---|---|---|---|---|---|---|
| 19 | yes | [PASS / PASS](task-19_trial-1.md) | [FAIL / FAIL](task-19_trial-2.md) | [PASS / PASS](task-19_trial-3.md) | [PASS / PASS](task-19_trial-4.md) | Database does not match the expected end state. |
| 3 | yes | [PASS / PASS](task-3_trial-1.md) | [PASS / PASS](task-3_trial-2.md) | [PASS / PASS](task-3_trial-3.md) | [PASS / PASS](task-3_trial-4.md) |  |
| 52 | no | [FAIL / FAIL](task-52_trial-1.md) | [FAIL / FAIL](task-52_trial-2.md) | [FAIL / FAIL](task-52_trial-3.md) | [FAIL / FAIL](task-52_trial-4.md) | Database does not match the expected end state. |
| 46 | yes | [PASS / PASS](task-46_trial-1.md) | [PASS / PASS](task-46_trial-2.md) | [PASS / PASS](task-46_trial-3.md) | [PASS / PASS](task-46_trial-4.md) |  |
| 41 | no | [PASS / PASS](task-41_trial-1.md) | [PASS / PASS](task-41_trial-2.md) | [PASS / PASS](task-41_trial-3.md) | [PASS / PASS](task-41_trial-4.md) |  |
| 22 | no | [PASS / PASS](task-22_trial-1.md) | [PASS / PASS](task-22_trial-2.md) | [PASS / PASS](task-22_trial-3.md) | [PASS / PASS](task-22_trial-4.md) |  |
| 16 | yes | [PASS / PASS](task-16_trial-1.md) | [PASS / PASS](task-16_trial-2.md) | [PASS / PASS](task-16_trial-3.md) | [PASS / PASS](task-16_trial-4.md) |  |
| 14 | no | [PASS / PASS](task-14_trial-1.md) | [PASS / PASS](task-14_trial-2.md) | [PASS / PASS](task-14_trial-3.md) | [PASS / PASS](task-14_trial-4.md) |  |
| 85 | no | [PASS / PASS](task-85_trial-1.md) | [PASS / PASS](task-85_trial-2.md) | [PASS / PASS](task-85_trial-3.md) | [PASS / PASS](task-85_trial-4.md) |  |
| 4 | yes | [PASS / PASS](task-4_trial-1.md) | [PASS / PASS](task-4_trial-2.md) | [PASS / PASS](task-4_trial-3.md) | [PASS / PASS](task-4_trial-4.md) |  |
| 112 | no | [PASS / PASS](task-112_trial-1.md) | [PASS / PASS](task-112_trial-2.md) | [PASS / PASS](task-112_trial-3.md) | [PASS / PASS](task-112_trial-4.md) |  |
| 6 | no | [PASS / PASS](task-6_trial-1.md) | [PASS / PASS](task-6_trial-2.md) | [PASS / PASS](task-6_trial-3.md) | [PASS / PASS](task-6_trial-4.md) |  |
| 105 | yes | [PASS / FAIL](task-105_trial-1.md) | [PASS / FAIL](task-105_trial-2.md) | [PASS / FAIL](task-105_trial-3.md) | [PASS / FAIL](task-105_trial-4.md) | Judge says not met: Agent should exchange both tea kettles (same style) to the items requested |
| 113 | yes | [PASS / PASS](task-113_trial-1.md) | [PASS / PASS](task-113_trial-2.md) | [PASS / PASS](task-113_trial-3.md) | [PASS / PASS](task-113_trial-4.md) |  |
| 47 | yes | [PASS / PASS](task-47_trial-1.md) | [PASS / PASS](task-47_trial-2.md) | [PASS / PASS](task-47_trial-3.md) | [PASS / PASS](task-47_trial-4.md) |  |
| 58 | no | [PASS / PASS](task-58_trial-1.md) | [PASS / PASS](task-58_trial-2.md) | [PASS / PASS](task-58_trial-3.md) | [PASS / PASS](task-58_trial-4.md) |  |
| 1 | no | [PASS / PASS](task-1_trial-1.md) | [PASS / PASS](task-1_trial-2.md) | [PASS / PASS](task-1_trial-3.md) | [PASS / PASS](task-1_trial-4.md) |  |
| 110 | yes | [PASS / FAIL](task-110_trial-1.md) | [PASS / FAIL](task-110_trial-2.md) | [PASS / FAIL](task-110_trial-3.md) | [PASS / FAIL](task-110_trial-4.md) | Judge says not met: Agent should modify user address |
| 15 | no | [PASS / PASS](task-15_trial-1.md) | [PASS / PASS](task-15_trial-2.md) | [PASS / PASS](task-15_trial-3.md) | [PASS / PASS](task-15_trial-4.md) |  |
| 73 | no | [PASS / PASS](task-73_trial-1.md) | [PASS / PASS](task-73_trial-2.md) | [PASS / PASS](task-73_trial-3.md) | [PASS / PASS](task-73_trial-4.md) |  |

## Tokens

| Role | Input | Output |
|---|---|---|
| user_sim | 701,187 | 65,035 |
| agent | 7,130,102 | 161,966 |
| judge | 201,830 | 6,220 |
| **total** | | **8,266,340** |
