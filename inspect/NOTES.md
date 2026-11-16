# Inspect, mapped onto our harness

Inspect (`inspect-ai`) is a framework for running evals, and `inspect-evals` is a library of ready-made evals built on it. We use its τ²-bench port (`inspect_evals/tau2_airline`) instead of our hand-built retail harness. The old harness is unchanged. This page covers the Inspect side.

## The six concepts

| Inspect term | What it means | Our harness equivalent |
|---|---|---|
| **Task** | One runnable eval: a dataset plus a solver plus a scorer. `tau2_airline` is a task. | `run.py` as a whole (it wires everything together) |
| **Dataset** | The list of samples (test cases). Each sample has an id, an input and a target. Here, one sample = one τ²-bench airline task: the customer's hidden scenario plus the gold answer. | `data/retail/tasks.json`, filtered by `tasks/fixed_set.json` |
| **Solver** | What produces the conversation. Here it's a loop: the customer simulator (Sonnet) speaks, then the agent (Haiku) calls tools and replies, repeating until the customer writes `###STOP###`, `###TRANSFER###` or `###OUT-OF-SCOPE###`, or 100 rounds pass. | `harness/simulate.py` (+ `harness/retail_tools.py` for the tools) |
| **Scorer** | Decides pass or fail for one finished sample. | `harness/grade.py` |
| **Epoch** | One repeat of the whole dataset. `--epochs 4` runs every task 4 times. | A "trial" (`--trials 4`) |
| **Log** | One `.eval` file per run (zipped JSON): config, every transcript, every model call, scores, token counts. `inspect view` shows it as a web page. | One `runs/<date>/` folder: `report.md` plus a `task-N_trial-M.md` per trial |

## Which model does what, and how it's set

- **Agent:** `--model anthropic/claude-haiku-5-5`. The port calls `get_model()` with no arguments, which means "the main model".
- **Customer simulator:** the port calls `get_model(role="user")`, so we set it with `--model-role user=anthropic/claude-sonnet-5-5`.
- **Grading model:** the airline grader doesn't use one (see below), so there's nothing to set.
- The port asks for temperature 0. These Claude models no longer accept a temperature setting, so Inspect drops it with a warning. Runs aren't deterministic, which was already true of our harness.

`inspect/run.sh` passes all of this and builds the viewer. `inspect/summarize.py` prints per-task results, pass^k, tokens and cost.

## How the port grades airline, and how that differs from our retail grader

**The port's airline grader** passes a task only if both of these hold:
1. **Database check:** it replays the task's gold actions on a fresh database and checks that the agent's final database is identical. A task whose gold actions change nothing (a refusal task, for example) passes as long as the agent also changes nothing.
2. **Communicated info:** each required fact (e.g. a refund amount) appears word for word, ignoring case and commas, somewhere in the agent's messages. Only 6 of the 50 airline tasks have such facts.

**Our retail grader** (`harness/grade.py`) checks three things: (1) the conversation ended normally, (2) the same database check, and (3) where the task requires it, an **LLM judge** (Sonnet) reads the conversation and confirms each natural-language assertion.

The differences that matter:
- **No LLM judge in the port's airline grader.** Every airline task carries natural-language assertions, but this grader ignores them. The port's README says a grading model is used for airline, but the code doesn't use one. Airline scores are therefore entirely code-based, the same idea as our "code-only" column.
- **No "ended normally" check.** A conversation that hits the 100-round cap is still graded on its database.
- **Errors are swallowed.** If a model call fails mid-conversation, the port prints a message and carries on rather than marking the sample as an error. That conversation can then score as a pass, for example on a task where doing nothing is the correct answer. `summarize.py` shows turn counts, and the run output should be checked for `Error in user_simulator_agent loop`.
- **Who speaks first.** In the port the customer opens the conversation. In our harness the agent opens with a fixed greeting.
- **Agent prompt.** The port uses its own short instruction block plus the airline policy. We can't swap in our `prompts/agent_v*.md` without writing our own solver.
- A cosmetic bug: database-check messages say "retail database" even for airline.

## Reading a transcript in the viewer

In the port, the roles in the main **Messages** tab are flipped. Messages labelled **assistant** are the *customer* (the simulator is the model being driven), and messages labelled **user** are the *agent's* replies. The agent's tool calls aren't in Messages. To see them, open the **Transcript** tab and look at the `model` events from `claude-haiku-5-5`, or look in **Store** → `StoredAgentState:AirlineAgent:messages`. The score's explanation is under **Scoring**.

## pass^k

Inspect reports `accuracy`, which is pass^1: the share of all task × epoch attempts that passed. It has no built-in "all epochs pass" measure, so `summarize.py` computes τ-bench's pass^k from the log. For each task, it takes the number of epochs passed (c) out of the number run (n) and computes C(c,k)/C(n,k), the chance that k randomly chosen epochs all pass, then averages that over tasks. When k equals the number of epochs, this is just the share of tasks that passed every time.

## Log size

The port keeps a copy of the 3.3 MB airline database in each transcript's state, about six times over, so each sample adds about 3 MB to the zipped log. A 20 × 4 run is about 250 MB, over GitHub's 100 MB per-file limit. `run.sh` therefore writes the full log to `inspect/logs-raw/` (not committed, and lost when the machine is reset) and a slimmed copy to `inspect/logs/` (`slim_log.py`: database snapshots removed; conversations, tool calls, scores and token usage kept; about 30 KB per sample). The viewer and `summarize.py` read the slimmed copies.
