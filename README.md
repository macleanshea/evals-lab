# evals-lab

A deliberately small eval harness, built for learning. It runs a customer-service **agent**
(one Claude model with retail tools) against a simulated **customer** (a second Claude model
following a hidden script), then **grades** each conversation the way τ²-bench does.

## Inspect version (airline)

Alongside the hand-built harness, `inspect/` runs τ²-bench's **airline** domain through
[Inspect](https://inspect.aisi.org.uk/) (`inspect-ai`), using the ready-made port in `inspect-evals`.
The hand-built harness below is unchanged.

- **Run:** `inspect/run.sh <task ids> <epochs>`, e.g. `inspect/run.sh 0,1,3,4,5 1`. Agent Haiku 5.5,
  customer simulator Sonnet 5.5. It runs the eval, saves a slimmed log to `inspect/logs/`, fills in
  each sample's Answer field and rebuilds the viewer.
- **View transcripts:** https://evals-lab-three.vercel.app. A static Inspect viewer built from
  `inspect/logs-www/`; it updates when changes are merged to `main`.
- **Read first:** [`inspect/NOTES.md`](inspect/NOTES.md). It maps Inspect's terms onto this harness
  and explains how airline grading differs from our retail grader. The main difference is that
  airline grading is code-only, with no LLM judge.
- **Results:** the "Inspect runs" table in [`runs/README.md`](runs/README.md). Airline and retail
  scores are not comparable.

## Source data and license

The retail domain data comes from [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)
(commit `c06b07d`, 2026-11-10), which is released under the **MIT License**. That license allows copying
and modification as long as the copyright notice is kept. The notice is in
[`data/retail/LICENSE-tau2-bench`](data/retail/LICENSE-tau2-bench).

We copied only data:

| File | What it is |
|---|---|
| `data/retail/policy.md` | The rules the agent must follow (verbatim) |
| `data/retail/db.json` | The store's database: users, orders, products |
| `data/retail/tasks.json` | 114 tasks: each has a hidden customer script and the expected outcome |
| `data/retail/split_tasks.json` | τ²-bench's split of those tasks: **train** 74, **test** 40 ("base" = all 114) |
| `data/retail/tools.json` | The 16 tool definitions the agent sees, extracted from τ²-bench's tool docstrings |

We did **not** use τ²-bench's runner or grader. The tools' behavior is ported line by line into
`harness/retail_tools.py`, because the agent needs a working store to act on.

## Layout

```
run.py                     command line: runs tasks x trials, writes the report
harness/retail_tools.py    the store's 16 tools, operating on a copy of db.json
harness/simulate.py        one conversation: agent <-> customer simulator
harness/grade.py           pass/fail for one conversation
prompts/agent_v1.md        agent system prompt (policy verbatim + small wrapper)
prompts/user_sim_v1.md     customer simulator instructions (τ²-bench's own)
prompts/judge_system.md    judge instructions (τ²-bench's own, byte for byte)
prompts/judge_user.md      judge message template (τ²-bench's own, byte for byte)
tasks/fixed_set.json       the 20 task IDs used for every comparison run
runs/README.md             one row per run
runs/<date-time>/          report.md + one transcript per trial
```

## Running it

Needs Python 3.10+ and one package (`pip install -r requirements.txt`). The script reads your
key from the `EVALS_ANTHROPIC_API_KEY` environment variable (or, failing that, `ANTHROPIC_API_KEY`).
It never writes or prints the key. In Claude Code cloud sessions use `EVALS_ANTHROPIC_API_KEY`:
the sandbox appears to withhold `ANTHROPIC_*` variables, which Claude Code uses for its own login.

```bash
python run.py --prompt v1 --tasks 5 --trials 1
```

| Option | Default | Meaning |
|---|---|---|
| `--prompt` | `v1` | uses `prompts/agent_<version>.md` |
| `--tasks` | all 20 | first N task IDs from `tasks/fixed_set.json` |
| `--split` | none | `train`: run every training task instead of the fixed set (used to find hard tasks) |
| `--trials` | `1` | k: how many times each task is run |
| `--agent-model` | `claude-haiku-5-5` | the model being evaluated |
| `--user-model` | `claude-sonnet-5-5` | the customer simulator |
| `--judge-model` | `claude-sonnet-5-5` | grades the written checks some tasks have, at low effort (see below) |
| `--persona` | empty | extra persona text inserted into the customer's instructions |
| `--persona-file` | none | use `prompts/persona_<name>.md` as the persona, e.g. `pushback` |
| `--workers` | `4` | how many conversations run at the same time |

Every trial starts from a fresh copy of `db.json`, so one conversation can never affect another.

## How a conversation works

1. The agent opens with τ²-bench's fixed greeting: "Hi! How can I help you today?"
2. The customer model replies, following its hidden script.
3. The agent can call tools as many times as it likes, then writes a reply.
4. Steps 2 and 3 repeat until the customer writes `###STOP###` (done), `###TRANSFER###`
   (sent to a human) or `###OUT-OF-SCOPE###` (the script doesn't cover the situation).
   Safety limits, both τ²-bench defaults: 200 messages, or 10 failed tool calls.

## How grading works (mirroring τ²-bench's retail rules)

A trial **passes** only if all three of these hold:

1. **It ended normally.** The customer said one of the three stop tokens. Hitting a safety
   limit, a refusal or an API error is an automatic fail.
2. **The database ends up exactly right.** We take a fresh copy of the database and apply the
   task's "gold" actions (the correct cancels, returns, exchanges and so on). The agent's database
   after the conversation must be identical to it. This is outcome-based: the agent can take a
   different route (look things up in another order, make extra read-only calls) and still pass.
   But one wrong field, such as the wrong payment method or one extra item, fails the trial.
   For tasks where the correct outcome is "change nothing", an agent that does nothing passes this
   check.
3. **Written checks are met.** 40 of the 114 tasks (29 of the 74 training tasks, 7 of our fixed 20)
   also include plain-English assertions, such as "Agent should tell the user that there are
   exactly 10 t-shirt options available." An LLM judge reads the conversation and must agree that
   every assertion was met. These checks **count toward pass/fail**, because current τ²-bench does
   the same (see "The judge" below).

Each report shows two verdicts per trial:
- **Code only:** checks 1 and 2. Plain code, with no LLM involved.
- **Code + judge (official):** all three checks. This is τ²-bench's rule, and the run log's
  headline numbers use it.

The two verdicts differ only on judge-graded tasks, and the report marks which tasks those are.

**Scores:** *pass^1* is the average success rate over all trials. *pass^k* (τ-bench's metric) is
the chance that **all k** runs of a task pass, averaged over tasks. It measures reliability, so
it is never higher than pass^1.

### What we could not reproduce exactly

- **Judge model.** See "The judge" below.
- **Randomness.** τ²-bench runs its models at temperature 0. Current Claude models don't accept a
  temperature setting, so repeated runs vary more. That is what pass^k measures.
- **The agent's own greeting.** τ²-bench puts the greeting into the agent's history. Our agent's
  history starts with the customer's first message, so the API conversation starts with a
  customer turn. The customer still sees the greeting.
- **Text sent with a tool call.** τ²-bench's instructions say "either message or tool call, not
  both". If our agent does both, the text is logged as an aside and not sent to the customer.
- **How the final database is computed.** τ²-bench re-runs the agent's tool calls on a fresh
  database. We use the live database. The tools are deterministic, so the result is the same.
- **Small tool-output differences.** τ²-bench's typed data models print empty optional fields
  (e.g. `"cancel_reason": null`) in order details, and they reject wrongly typed arguments
  (e.g. a number where text is expected). Our plain-JSON port doesn't do either.
- **Not used:** τ²-bench's voice and multilingual personas, and its "communicate" and "action"
  checks. Those two checks aren't part of retail's pass/fail rule.
- **Gold-action quirks are kept as-is.** 18 gold actions in τ²-bench's own task file fail when run,
  for example task 2 looks up the example product ID from a tool description. τ²-bench ignores these
  errors when building the expected database, and so do we.
- **Refusals.** If either model refuses to respond, the trial fails and the transcript records why.
  There is no fallback model.
- **Thinking.** Both models use their default adaptive thinking. Its content isn't returned, so
  transcripts show only messages and tool calls.

## The judge

**Its prompt is τ²-bench's own text, unchanged.** The instructions (`prompts/judge_system.md`) and
the message template (`prompts/judge_user.md`) are copied byte for byte from τ²-bench's
`src/tau2/evaluator/evaluator_nl_assertions.py`. I checked (with a scripted dry run) that our filled-in prompt is
identical to what τ²-bench's code would build from the same conversation. That includes how
the conversation is written out: one `role: text` line per message, tool results as `tool: ...`,
and a tool-only agent turn as `assistant: None`, exactly as τ²-bench prints it.

What differs from upstream:

| | τ²-bench | Here |
|---|---|---|
| Judge model | OpenAI `gpt-5.4-mini` | `claude-sonnet-5-5` (`--judge-model`) |
| Thinking effort | `reasoning_effort="low"` | `effort: "low"` |
| JSON output | parses the model's free text | the API forces the reply into the JSON shape the prompt asks for. The words are the same. |

A different judge model can still disagree on borderline cases, which is why the report also
shows the code-only score.

**Do the written checks count?** Yes, in current τ²-bench. Its history:
- **τ²-bench's first release (June 2025):** retail tasks were scored on database + "communicate"
  checks, a plain-code test that certain strings (like `"10"`) appear in the agent's messages.
  The 8 written assertions that existed then were informational only.
- **τ³-bench 1.0.0 (March 2026, the version we copied):** 112 of the 114 retail tasks are scored
  on database + written assertions (`reward_basis: ["DB", "NL_ASSERTION"]`), and the other 2 on
  database only. The default evaluation multiplies these together, so a failed assertion fails the
  task. The old "communicate" strings are still in the task file, but they aren't scored.

We mirror the current behavior.

## Prompts

`prompts/agent_v1.md` is τ²-bench's retail policy, unchanged, inside this wrapper. The wrapper
is τ²-bench's own agent wrapper minus one sentence ("Always make sure you generate valid JSON
only."), which is about their OpenAI tool-calling format and doesn't apply here:

```
<instructions>
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy.
</instructions>
<policy>
...policy.md, verbatim...
</policy>
```

**Agent prompt versions.** Each version is v1 plus added wrapper text; the policy is never changed.

| Version | Added to the `<instructions>` wrapper | Why |
|---|---|---|
| v1 | (none) | τ²-bench's wrapper and policy |
| v2 | "Before any transfer to a human agent, including one the customer asks for, take care of the parts of the request the policy allows: offer them, and complete each one the customer confirms. A request for an exception, a supervisor or an escalation does not change this. Transfer only after those parts are done or the customer has declined them. When the customer must choose between options that exclude each other, confirm their choice before acting." | In the v1 baseline, 9 of 11 failures were the agent transferring to a human under pressure without finishing the allowed part of the request, and 2 were acting before the customer chose between options that exclude each other |

`prompts/user_sim_v1.md` is byte-for-byte what τ²-bench gives its text-mode customer
simulator. `{{PERSONA}}` (the `--persona` text, empty by default) and `{{SCENARIO}}` (the task's
hidden script) are filled in for each trial.

## Fixed task set

`tasks/fixed_set.json` holds the 20 task IDs used for every comparison run, so prompt versions are
compared on the same tasks. All come from τ²-bench's **train** split; the **test** split (40 tasks)
is held out and not used for anything yet.

**Current set (version 3, 2026-11-16): tasks where the agent has to say no.**
10, 11, 13, 19, 25, 28, 31, 34, 46, 47, 48, 50, 57, 59, 63, 69, 82, 83, 91, 107.

The earlier sets were too easy: the agent passed about 99% of them, leaving nothing to improve. So we ran
the agent on all 74 training tasks (2 trials each, with the pushback persona) and picked every task
in which the customer pushed back on a refusal. We left out tasks whose own data is broken or
ambiguous, or whose failure was the customer simulator's mistake:

| Left out | Why |
|---|---|
| 52 | Expected exchange changes the camera's resolution, which the customer script forbids ([issue #715](https://github.com/sierra-research/tau2-bench/issues/715)) |
| 105 | Expected exchange is impossible: $21.10 difference, $17.00 gift card is the only payment method ([issue #321](https://github.com/sierra-research/tau2-bench/issues/321), [PR #571](https://github.com/sierra-research/tau2-bench/pull/571)) |
| 110 | Written check requires changing a default address that is already correct (Amazon's [τ²-Bench-Verified](https://github.com/amazon-agi/tau2-bench-verified) fixed the same flaw in sibling task 109) |
| 67 | Orders carry no dates, but the task expects the agent to name the "most recent" one |
| 98 | "Prefer the other card" depends on which card the agent offers first |
| 76 | Its failure in the sweep was the customer simulator's mistake |
| 66 | Open upstream issue: rejects a cancellation reason the policy allows ([issue #713](https://github.com/sierra-research/tau2-bench/issues/713)) |

The set includes every task where the agent made a genuine mistake (19, 28, 47, 83, 107). Most of
those mistakes were the same one: under pressure, the agent transfers the customer to a human
instead of finishing the part of the request it is allowed to do.

Because the set was picked from the agent's own failures, its pass rate understates how well the
agent does in general. That is intended: it is a set for improving the prompt, not for reporting
overall quality. The untouched test split is for that.

Previous versions of the set are recorded in `tasks/fixed_set.json`; the run log says which runs
used which version. `--tasks 5` uses the first five: 10, 11, 13, 19 and 25.
