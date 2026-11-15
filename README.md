# evals-lab

A deliberately small eval harness, built for learning. It runs a customer-service **agent**
(one Claude model with retail tools) against a simulated **customer** (a second Claude model
following a hidden script), then **grades** each conversation the way τ²-bench does.

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
| `data/retail/split_tasks.json` | τ²-bench's train/test split of those tasks |
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
tasks/fixed_20.json        the 20 task IDs used for every comparison run
runs/README.md             one row per run
runs/<date-time>/          report.md + one transcript per trial
```

## Running it

Needs Python 3.10+ and one package (`pip install -r requirements.txt`). The script reads your
key from the `ANTHROPIC_API_KEY` environment variable. It never writes or prints the key.

```bash
python run.py --prompt v1 --tasks 5 --trials 1
```

| Option | Default | Meaning |
|---|---|---|
| `--prompt` | `v1` | uses `prompts/agent_<version>.md` |
| `--tasks` | `20` | first N task IDs from `tasks/fixed_20.json` |
| `--trials` | `1` | k: how many times each task is run |
| `--agent-model` | `claude-haiku-5-5` | the model being evaluated |
| `--user-model` | `claude-sonnet-5-5` | the customer simulator |
| `--judge-model` | `claude-sonnet-5-5` | grades the written checks some tasks have (see below) |
| `--persona` | empty | extra persona text inserted into the customer's instructions |
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
3. **Written checks are met.** 40 of the 114 tasks (4 of our fixed 20) also include plain-English
   assertions, such as "Agent should tell the user that there are 10 t-shirt options available."
   An LLM judge reads the conversation and must agree that every assertion was met. We use
   τ²-bench's exact judge instructions.

**Scores:** *pass^1* is the average success rate over all trials. *pass^k* (τ-bench's metric) is
the chance that **all k** runs of a task pass, averaged over tasks. It measures reliability, so
it is never higher than pass^1.

### What we could not reproduce exactly

- **Judge model.** τ²-bench's judge is an OpenAI model (`gpt-5.4-mini`, low reasoning). We use
  Claude (`--judge-model`). The instructions are identical, but a different judge can disagree
  on borderline cases. We also force the judge's answer into valid JSON (structured output);
  τ²-bench just parses its text.
- **Judge's view of tool calls.** τ²-bench prints turns that contain only tool calls as empty
  "assistant" lines. We leave those lines out and keep the tool results.
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

`prompts/user_sim_v1.md` is byte-for-byte what τ²-bench gives its text-mode customer
simulator. `{{PERSONA}}` (the `--persona` text, empty by default) and `{{SCENARIO}}` (the task's
hidden script) are filled in for each trial.

## Fixed task set

`tasks/fixed_20.json` holds 20 task IDs, drawn once (random seed 42) from τ²-bench's held-out
**test** split. Every comparison run uses this list, so prompt versions are compared on the same
tasks. `--tasks 5` uses the first five.
