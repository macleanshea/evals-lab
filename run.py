"""Run the eval: N tasks x k trials, then write runs/<date-time>/ and log the run.

Example:
    python run.py --prompt v1 --tasks 5 --trials 1
"""

import argparse
import datetime
import json
import math
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
    p.add_argument("--tasks", type=int, default=20, help="first N tasks of tasks/fixed_20.json")
    p.add_argument("--trials", type=int, default=1, help="k trials per task")
    p.add_argument("--agent-model", default="claude-haiku-5-5")
    p.add_argument("--user-model", default="claude-sonnet-5-5")
    p.add_argument("--judge-model", default="claude-sonnet-5-5",
                   help="grades the natural-language assertions some tasks have")
    p.add_argument("--persona", default="", help="optional extra persona text for the customer")
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
    except anthropic.APIError as e:
        log, usage = [], {}
        verdict = {"passed": False, "ended_because": "api_error", "db_match": None,
                   "db_diffs": [], "nl_results": None, "reason": f"API error: {e}"}
    print(f"  task {task['id']} trial {trial}: {'PASS' if verdict['passed'] else 'FAIL'}"
          f" - {verdict['reason'][:100]}", flush=True)
    return {"task": task, "trial": trial, "log": log, "usage": usage, "verdict": verdict}


def pass_hat_k(results, k):
    """τ-bench's pass^k: chance that k random trials of a task ALL pass, averaged over tasks."""
    by_task = {}
    for r in results:
        by_task.setdefault(r["task"]["id"], []).append(r["verdict"]["passed"])
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
           f"**Verdict: {'PASS' if v['passed'] else 'FAIL'}** - {v['reason']}", "",
           "## Grader details", "",
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
        elif m["who"] == "agent_aside":
            out += [f"_Agent note sent with a tool call (not shown to customer):_ {m['text']}", ""]
        elif m["who"] == "tool":
            label = "Tool error" if m["error"] else "Result"
            out += [f"> **Tool call:** `{m['name']}` `{json.dumps(m['args'])}`  ",
                    f"> **{label}:** `{m['output']}`", ""]
    path.write_text("\n".join(out))


def main():
    args = parse_args()
    cfg = {"agent_model": args.agent_model, "user_model": args.user_model,
           "judge_model": args.judge_model, "persona": args.persona}
    agent_system = (ROOT / "prompts" / f"agent_{args.prompt}.md").read_text()
    tools = json.loads((DATA / "tools.json").read_text())
    db_text = (DATA / "db.json").read_text()
    all_tasks = {t["id"]: t for t in json.loads((DATA / "tasks.json").read_text())}
    task_ids = json.loads((ROOT / "tasks" / "fixed_20.json").read_text())["task_ids"][:args.tasks]

    client = anthropic.Anthropic(max_retries=6)  # reads ANTHROPIC_API_KEY from the environment
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
    tokens = total_tokens(results)
    grand = sum(u["input"] + u["output"] for u in tokens.values())
    date = started.strftime("%Y-%m-%d %H:%M")

    summary = ["| Prompt | Tasks x trials | pass^1 | pass^k (k=%d) | Total tokens |" % k,
               "|---|---|---|---|---|",
               f"| {args.prompt} | {len(task_ids)} x {k} | {p1:.2f} | {pk:.2f} | {grand:,} |"]
    report = [f"# Run {run_dir.name}", "",
              f"Agent `{args.agent_model}` with `prompts/agent_{args.prompt}.md`; "
              f"customer simulator `{args.user_model}`; judge `{args.judge_model}`; "
              f"persona: {repr(args.persona) if args.persona else '(empty)'}", "",
              "## Summary", "", *summary, "",
              "## Per-task results", "", "| Task | " + " | ".join(f"Trial {i}" for i in range(1, k + 1))
              + " | Reason (first failing trial) |", "|---" * (k + 2) + "|"]
    for tid in task_ids:
        rs = sorted((r for r in results if r["task"]["id"] == tid), key=lambda r: r["trial"])
        cells = [f"[{'PASS' if r['verdict']['passed'] else 'FAIL'}](task-{tid}_trial-{r['trial']}.md)"
                 for r in rs]
        fail = next((r["verdict"]["reason"] for r in rs if not r["verdict"]["passed"]), "")
        report.append(f"| {tid} | " + " | ".join(cells) + f" | {fail.replace('|', '/')} |")
    report += ["", "## Tokens", "", "| Role | Input | Output |", "|---|---|---|"]
    report += [f"| {role} | {u['input']:,} | {u['output']:,} |" for role, u in tokens.items()]
    report += [f"| **total** | | **{grand:,}** |"]
    (run_dir / "report.md").write_text("\n".join(report) + "\n")

    log_path = ROOT / "runs" / "README.md"
    if not log_path.exists():
        log_path.write_text("# Run log\n\nOne row per run. Click a date for the full report.\n\n"
                            "| Date | Prompt | Tasks x trials | pass^1 | pass^k |\n|---|---|---|---|---|\n")
    with log_path.open("a") as f:
        f.write(f"| [{date}]({run_dir.name}/report.md) | {args.prompt} | "
                f"{len(task_ids)} x {k} | {p1:.2f} | {pk:.2f} |\n")

    print("\n" + "\n".join(summary))
    print(f"\nReport: {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
