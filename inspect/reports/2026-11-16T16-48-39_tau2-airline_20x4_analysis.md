# Run 2026-11-16 16:48: airline 20 × 4, analysis

> **Partly superseded (2026-11-17):** the "refused an allowed action" failures (7, 9, 14, 23, 27) and sample 33 turned out to be wrong expected answers, not agent mistakes. See [`2026-11-17_review.md`](2026-11-17_review.md) and [`../suspect_samples.json`](../suspect_samples.json).

Run: `inspect/logs/2026-11-16T16-48-39-00-00_tau2-airline_RCuQu5GYUMrKiPcEVyBNAQ.eval`. Per-task results are in [`2026-11-16T16-48-39_tau2-airline_20x4.txt`](2026-11-16T16-48-39_tau2-airline_20x4.txt). Agent: Haiku 5.5. Customer simulator: Sonnet 5.5. pass^1 0.64, pass^4 0.55.

**The score we optimise is the grader's**: the port's airline grader, which checks the database and any required facts. The Target items in the Answer field come from an LLM judge and are for diagnosis only. They are not part of the score, and they are not a target to improve on their own.

## Where the grader score is lost

These are the 6 tasks that failed in every epoch (29 of 80 samples failed in total). The failure types come from comparing the agent's database changes with the expected ones.

| Failure type | Tasks | What the agent did |
|---|---|---|
| Refused an allowed action | 7, 9, 14, 23, 27 | Declined to cancel, book or issue a certificate that the expected answer requires. Example: task 14 applied the payment rule for flight *changes* to a *new* booking and refused a mix of certificate, gift cards and credit card. |
| Wrong bag fee | 33 (also 17, epoch 2) | Made the right change but charged the wrong number of paid bags: 0 instead of 2 in task 33, and 1 instead of 0 in task 17. |
| Did something it shouldn't (sometimes) | 5 | Cancelled a booking and issued a certificate to get a customer compensation (failed 1 of 4 epochs; also failed in the first 5-task run). |

So the biggest lever on the grader score is **over-refusal**: the agent turning down actions the policy allows. Fee calculation comes second.

## Where the grader and the Target items disagree (8 of 80 samples)

### Passed, but a Target item was marked Fail (6 of 51 passing samples)
- **Task 5, epochs 1 and 3.** "Agent does not offer any compensation." The agent offered a $200 certificate, conditional on changing or cancelling the booking. The customer declined, so the database was unchanged and the sample passed. When a customer accepted the same offer (first 5-task run), the sample failed. The grader only sees the database, so it can't catch a wrong offer that the customer refuses. As far as we can tell, original τ²-bench grades airline the same way.
- **Task 1, all 4 epochs.** "Agent should not include any unnecessary information." The judge considered the replies too wordy. This is a judgement call about style, and the main point of the task (refusing the cancellation) was met.

### Failed, but every Target item was marked Pass (2 of 29 failing samples)
- **Task 17, epoch 2.** The agent set the correct 3 bags but charged for 1 that should have been free. The Target items don't mention fees, so they all genuinely passed. The grader correctly failed it.
- **Task 17, epoch 3.** The customer simulator read "add 3 checked bags" as 3 on top of the bags already included and asked for that. The agent did what was asked (5 bags, 3 paid), so the sample failed through no fault of the agent. The task wording is ambiguous. The judge also passed "bags updated to 3", which is a stretch.

## Open question
- **Task 17** may belong on an exclusion list for ambiguous task data, like the retail exclusions in `tasks/fixed_set.json`, if it keeps failing because of the simulator. Undecided.

Method: verdicts are from one judge call per sample (`inspect/annotate_answers.py`), and the judge can be wrong.
