"""Run the eval: N tasks x k trials, then write runs/<date-time>/ and log the run.

Example:
    python run.py --prompt v1 --tasks 5 --trials 1
"""

import argparse
import datetime
import json
import math
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor

import anthropic

from harness.grade import grade
from harness.simulate import run_trial, scenario_text

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data" / "retail"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompt", default="v1", help="agent prompt version: v1 -> prompts/agent_v1.md")
    p.add_argument("--tasks", type=int, default=None, help="first N tasks of tasks/fixed_set.json (default: all 20)")
    p.add_argument("--trials", type=int, default=1, help="k trials per task")
    p.add_argument("--agent-model", default="claude-haiku-5-5")
    p.add_argument("--user-model", default="claude-sonnet-5-5")
    p.add_argument("--judge-model", default="claude-sonnet-5-5",
                   help="grades the natural-language assertions some tasks have")
    p.add_argument("--persona", default="", help="optional extra persona text for the customer")
    p.add_argument("--persona-file", default="",
                   help="use prompts/persona_<name>.md as the persona, e.g. --persona-file pushback")
    p.add_argument("--workers", type=int, default=4, help="trials run in parallel")
    return p.parse_args()


def one_trial(client, cfg, task, trial, agent_system, tools, db_text):
    user_system = ((ROOT / "prompts" / "user_sim_v1.md").read_text()
                   .replace("{{PERSONA}}", cfg["persona"])
                   .replace("{{SCENARIO}}", scenario_text(task)))
    db = json.loads(db_text)  # fresh copy of the database for every trial
    try:
        log, ended, usage = run_trial(client, task, db, agent_system, user_system, tools, cfg)
        verdict = grade(client, cfg["judge_model"], task, db, json.loads(db_text), log, ended, usage)
    except Exception as e:  # any failure fails this trial only; the rest of the run carries on
        kind = "api_error" if isinstance(e, anthropic.APIError) else "harness_error"
        log, usage = [], {}
        criteria = task["evaluation_criteria"]
        verdict = {"passed": False, "code_passed": False,
                   "judge_graded": "NL_ASSERTION" in criteria["reward_basis"]
                                   and bool(criteria.get("nl_assertions")),
                   "ended_because": kind, "db_match": None, "db_diffs": [], "nl_results": None,
                   "reason": f"{'API' if kind == 'api_error' else 'Unexpected'} error "
                             f"({type(e).__name__}): {e}"}
    print(f"  task {task['id']} trial {trial}: code-only {pf(verdict['code_passed'])}, "
          f"code+judge {pf(verdict['passed'])} - {verdict['reason'][:100]}", flush=True)
    return {"task": task, "trial": trial, "log": log, "usage": usage, "verdict": verdict}


def pf(ok):
    return "PASS" if ok else "FAIL"


def pass_hat_k(results, k, key="passed"):
    """τ-bench's pass^k: chance that k random trials of a task ALL pass, averaged over tasks.
    key="passed" scores the official verdict; key="code_passed" the code-only one."""
    by_task = {}
    for r in results:
        by_task.setdefault(r["task"]["id"], []).append(r["verdict"][key])
    scores = [math.comb(sum(v), k) / math.comb(len(v), k) for v in by_task.values()]
    return sum(scores) / len(scores)


def total_tokens(results):
    totals = {}
    for r in results:
        for role, u in r["usage"].items():
            t = totals.setdefault(role, {"input": 0, "output": 0})
            t["input"] += u["input"]
            t["output"] += u["output"]
    return totals


def write_transcript(path, r):
    t, v = r["task"], r["verdict"]
    out = [f"# Task {t['id']} - trial {r['trial']}", "",
           f"**Verdict (code + judge, official): {pf(v['passed'])}** - {v['reason']}  ",
           f"Code-only verdict: {pf(v['code_passed'])}"
           + ("" if v["judge_graded"] else " (this task has no judge checks, so both verdicts are the same)"),
           "", "## Grader details", "",
           f"- Conversation ended because: `{v['ended_because']}`",
           f"- Database matches expected end state: {v['db_match']}"]
    out += [f"  - {d}" for d in v["db_diffs"]]
    if v["nl_results"] is not None:
        out.append("- Judge's assertion checks:")
        for n in v["nl_results"]:
            out.append(f"  - {'MET' if n['metExpectation'] else 'NOT MET'}: "
                       f"{n['expectedOutcome']} - _{n['reasoning']}_")
    out.append(f"- Tokens used: {json.dumps(r['usage'])}")
    out += ["", "## Customer's hidden script", "", "```", scenario_text(t), "```", "",
            "## Expected (gold) actions", ""]
    out += [f"- `{a['name']}` `{json.dumps(a['arguments'])}`"
            for a in t["evaluation_criteria"]["actions"] or []]
    out += ["", "## Conversation", ""]
    for m in r["log"]:
        if m["who"] == "agent":
            out += [f"**Agent:** {m['text']}", ""]
        elif m["who"] == "user":
            out += [f"**Customer:** {m['text']}", ""]
        elif m["who"] == "agent_tool_turn" and m["text"]:
            out += [f"_Agent text sent with a tool call (not shown to customer):_ {m['text']}", ""]
        elif m["who"] == "tool":
            label = "Tool error" if m["error"] else "Result"
            out += [f"> **Tool call:** `{m['name']}` `{json.dumps(m['args'])}`  ",
                    f"> **{label}:** `{m['output']}`", ""]
    path.write_text("\n".join(out))


def main():
    args = parse_args()
    persona_label = "none"
    if args.persona_file:
        args.persona = (ROOT / "prompts" / f"persona_{args.persona_file}.md").read_text().strip()
        persona_label = args.persona_file
    elif args.persona:
        persona_label = "custom (see report)"
    cfg = {"agent_model": args.agent_model, "user_model": args.user_model,
           "judge_model": args.judge_model, "persona": args.persona}
    agent_system = (ROOT / "prompts" / f"agent_{args.prompt}.md").read_text()
    tools = json.loads((DATA / "tools.json").read_text())
    db_text = (DATA / "db.json").read_text()
    all_tasks = {t["id"]: t for t in json.loads((DATA / "tasks.json").read_text())}
    task_ids = json.loads((ROOT / "tasks" / "fixed_set.json").read_text())["task_ids"][:args.tasks]

    # The key comes only from the environment, never from a file. EVALS_ANTHROPIC_API_KEY is
    # checked first because cloud sessions may hold back ANTHROPIC_* variables for their own use.
    key = os.environ.get("EVALS_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("No API key: set EVALS_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY).")
    client = anthropic.Anthropic(api_key=key, max_retries=6)
    started = datetime.datetime.now()
    run_dir = ROOT / "runs" / started.strftime("%Y-%m-%d_%H%M%S")
    run_dir.mkdir(parents=True)
    print(f"Running {len(task_ids)} tasks x {args.trials} trials, prompt {args.prompt} -> {run_dir}")

    jobs = [(all_tasks[i], k) for i in task_ids for k in range(1, args.trials + 1)]
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(
            lambda j: one_trial(client, cfg, j[0], j[1], agent_system, tools, db_text), jobs))

    for r in results:
        write_transcript(run_dir / f"task-{r['task']['id']}_trial-{r['trial']}.md", r)

    k = args.trials
    p1, pk = pass_hat_k(results, 1), pass_hat_k(results, k)
    c1, ck = pass_hat_k(results, 1, "code_passed"), pass_hat_k(results, k, "code_passed")
    tokens = total_tokens(results)
    grand = sum(u["input"] + u["output"] for u in tokens.values())
    date = started.strftime("%Y-%m-%d %H:%M")
    judged = [tid for tid in task_ids if any(
        r["task"]["id"] == tid and r["verdict"]["judge_graded"] for r in results)]

    summary = [f"| Grading | Tasks x trials | pass^1 | pass^k (k={k}) |",
               "|---|---|---|---|",
               f"| Code only | {len(task_ids)} x {k} | {c1:.2f} | {ck:.2f} |",
               f"| Code + judge (official) | {len(task_ids)} x {k} | {p1:.2f} | {pk:.2f} |",
               "", f"Prompt `{args.prompt}`. Total tokens: {grand:,}. "
               f"Judge-graded tasks: {', '.join(judged) or 'none'}."]
    report = [f"# Run {run_dir.name}", "",
              f"Agent `{args.agent_model}` with `prompts/agent_{args.prompt}.md`; "
              f"customer simulator `{args.user_model}`; judge `{args.judge_model}`; "
              f"persona: {persona_label}", "",
              *([f"> {args.persona}", ""] if args.persona else []),
              "## Summary", "", *summary, "",
              "**Code only** = the conversation ended normally and the database matches. "
              "**Code + judge** additionally requires the LLM judge to accept every written "
              "check; this is τ²-bench's own pass rule. They differ only on judge-graded tasks.", "",
              "## Per-task results", "",
              "Each cell: code-only / code + judge. Click for the transcript.", "",
              "| Task | Judge-graded | " + " | ".join(f"Trial {i}" for i in range(1, k + 1))
              + " | Reason (first trial failing the official verdict) |", "|---" * (k + 3) + "|"]
    for tid in task_ids:
        rs = sorted((r for r in results if r["task"]["id"] == tid), key=lambda r: r["trial"])
        cells = [f"[{pf(r['verdict']['code_passed'])} / {pf(r['verdict']['passed'])}]"
                 f"(task-{tid}_trial-{r['trial']}.md)" for r in rs]
        fail = next((r["verdict"]["reason"] for r in rs if not r["verdict"]["passed"]), "")
        report.append(f"| {tid} | {'yes' if tid in judged else 'no'} | " + " | ".join(cells)
                      + f" | {fail.replace('|', '/')} |")
    report += ["", "## Tokens", "", "| Role | Input | Output |", "|---|---|---|"]
    report += [f"| {role} | {u['input']:,} | {u['output']:,} |" for role, u in tokens.items()]
    report += [f"| **total** | | **{grand:,}** |"]
    (run_dir / "report.md").write_text("\n".join(report) + "\n")

    log_path = ROOT / "runs" / "README.md"
    if not log_path.exists():
        log_path.write_text("# Run log\n\nOne row per run. Click a date for the full report. "
                            "Official scores = code + judge (τ²-bench's rule); code-only shown for reference.\n\n"
                            "| Date | Prompt | Persona | Tasks x trials | pass^1 | pass^k | pass^1 code-only | pass^k code-only |\n"
                            "|---|---|---|---|---|---|---|---|\n")
    with log_path.open("a") as f:
        f.write(f"| [{date}]({run_dir.name}/report.md) | {args.prompt} | {persona_label} | "
                f"{len(task_ids)} x {k} | {p1:.2f} | {pk:.2f} | {c1:.2f} | {ck:.2f} |\n")

    print("\n" + "\n".join(summary))
    print(f"\nReport: {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
