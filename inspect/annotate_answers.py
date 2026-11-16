"""Fill the viewer's "Answer" field for each sample of a (slimmed) Inspect τ²-bench airline log.

The port's grader leaves Answer blank. This writes, per sample:
  1. Yes / No for each item in the Target (the task's natural-language assertions),
     decided by an LLM judge reading the conversation. The port does NOT grade these
     assertions; this is for reading only and never changes the score.
     Judge: τ²-bench's own judge prompt (prompts/judge_*.md, the same text our retail
     grader uses), model claude-sonnet-5-5, effort "low" as in τ²-bench.
  2. Anything the agent did that the task did not expect: database-changing tool calls
     (and transfers to a human) that are not in the task's expected actions, plus
     expected ones the agent never made. Compared in code, no model involved.

The judge's per-item reasoning is kept in the score's metadata (Scoring tab).
Samples already annotated are skipped, so re-running costs nothing.
Usage: python inspect/annotate_answers.py <slimmed.eval> [<slimmed.eval> ...]
"""
import json
import os
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import anthropic
from inspect_ai.log import read_eval_log, write_eval_log

from inspect_evals.tau2.utils import deep_equal_unordered

ROOT = pathlib.Path(__file__).parent.parent
JUDGE_SYSTEM = (ROOT / "prompts" / "judge_system.md").read_text()
JUDGE_USER = (ROOT / "prompts" / "judge_user.md").read_text()
JUDGE_MODEL = "claude-sonnet-5-5"
# Same shape as harness/grade.py: forces valid JSON in the form the prompt asks for.
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {"expectedOutcome": {"type": "string"},
                       "reasoning": {"type": "string"},
                       "metExpectation": {"type": "boolean"}},
        "required": ["expectedOutcome", "reasoning", "metExpectation"],
        "additionalProperties": False}}},
    "required": ["results"],
    "additionalProperties": False,
}
# Tools that change the airline database, plus handing over to a human.
NOTABLE = {"book_reservation", "cancel_reservation", "send_certificate",
           "update_reservation_baggages", "update_reservation_flights",
           "update_reservation_passengers", "transfer_to_human_agents"}
DONE_KEY = "nl_assertions_judge"  # in score.metadata


def fmt(name, args):
    if name == "transfer_to_human_agents":
        return "transfer_to_human_agents"
    return f"{name}({', '.join(f'{k}={json.dumps(v)}' for k, v in args.items())})"


def conversation_text(messages):
    """τ²-bench's judge format: one "role: content" line per message (agent = assistant)."""
    lines = []
    for m in messages:
        if m.role == "system":
            continue
        lines.append(f"{m.role}: {m.text}")
    return "\n".join(lines)


def judge(client, messages, assertions):
    prompt = (JUDGE_USER.replace("{{CONVERSATION}}", conversation_text(messages))
              .replace("{{ASSERTIONS}}", str(assertions)))
    r = client.messages.create(
        model=JUDGE_MODEL, max_tokens=16000, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}})
    if r.stop_reason == "refusal":
        return None, r.usage
    text = next(b.text for b in r.content if b.type == "text")
    return json.loads(text)["results"], r.usage


def action_diff(sample):
    expected = [a for a in sample.metadata["task"]["evaluation_criteria"]["actions"] or []
                if a["name"] in NOTABLE]
    errors = {m.tool_call_id for m in sample.messages if m.role == "tool" and m.error}
    taken = [(tc.function, tc.arguments, tc.id in errors)
             for m in sample.messages if m.role == "assistant"
             for tc in (m.tool_calls or []) if tc.function in NOTABLE]

    def same(name, args, a):
        if name != a["name"]:
            return False
        return name == "transfer_to_human_agents" or deep_equal_unordered(args, a["arguments"])

    unexpected = [fmt(n, a) + (" — failed with an error" if err else "")
                  for n, a, err in taken if not any(same(n, a, e) for e in expected)]
    missing = [fmt(e["name"], e["arguments"]) for e in expected
               if not any(same(n, a, e) for n, a, err in taken if not err)]
    return unexpected, missing


def answer_text(results, assertions, unexpected, missing):
    lines = []
    if results is None:
        lines.append("Target items: the judge declined to assess this conversation.")
    else:
        for a, r in zip(assertions, results):
            lines.append(f"- **{'Yes' if r['metExpectation'] else 'No'}**: {a}")
    lines.append("")
    lines.append("**Also did:** " + ("; ".join(unexpected) if unexpected else "nothing else"))
    if missing:
        lines.append("")
        lines.append("**Expected but not done:** " + "; ".join(missing))
    return "\n".join(lines)


def annotate(path, client, usage_total):
    log = read_eval_log(path)
    todo = [s for s in log.samples if DONE_KEY not in (next(iter(s.scores.values())).metadata or {})]

    def work(s):
        assertions = s.metadata["task"]["evaluation_criteria"].get("nl_assertions") or []
        results, usage = (judge(client, s.messages, assertions) if assertions else ([], None))
        return s, assertions, results, usage

    with ThreadPoolExecutor(max_workers=8) as pool:
        for s, assertions, results, usage in pool.map(work, todo):
            if usage:
                usage_total["input"] += usage.input_tokens
                usage_total["output"] += usage.output_tokens
            unexpected, missing = action_diff(s)
            score = next(iter(s.scores.values()))
            score.answer = answer_text(results, assertions, unexpected, missing)
            score.metadata = {**(score.metadata or {}), DONE_KEY: {
                "model": JUDGE_MODEL, "results": results,
                "note": "For reading only. The port's airline grader does not use these assertions."}}
    write_eval_log(log, path)
    print(f"Annotated {len(todo)} of {len(log.samples)} samples in {path}")


def main(paths):
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("EVALS_ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    usage = {"input": 0, "output": 0}
    for p in paths:
        annotate(p, client, usage)
    cost = usage["input"] * 2 / 1e6 + usage["output"] * 10 / 1e6
    print(f"Judge tokens: input {usage['input']:,}, output {usage['output']:,} -> ${cost:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
