"""Grader: decides PASS/FAIL for one trial, mirroring τ²-bench's retail rules.

A trial passes only if ALL of these hold:
  1. The conversation ended normally (the customer sent a stop token).
  2. Database check: the database after the conversation is identical to the
     database you get by applying the task's "gold" actions to a fresh copy.
  3. Natural-language assertions (only some tasks have them): an LLM judge
     reads the conversation and confirms every assertion was met.

We also report a "code-only" verdict (checks 1 and 2 only) next to the official
one (all three), so you can see how much the judge changes the score.
"""

import json
import pathlib

from harness.retail_tools import call_tool

ROOT = pathlib.Path(__file__).parent.parent
# Both judge prompts are τ²-bench's own text (src/tau2/evaluator/evaluator_nl_assertions.py),
# copied byte for byte. {{CONVERSATION}} and {{ASSERTIONS}} are filled in per trial.
JUDGE_SYSTEM = (ROOT / "prompts" / "judge_system.md").read_text()
JUDGE_USER = (ROOT / "prompts" / "judge_user.md").read_text()

# Not part of τ²-bench: forces the judge's reply to be valid JSON in the shape its prompt asks for.
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


def expected_db(task, fresh_db):
    """Apply the gold actions to a fresh database (errors ignored, as in τ²-bench)."""
    for action in task["evaluation_criteria"]["actions"] or []:
        call_tool(fresh_db, action["name"], action["arguments"])
    return fresh_db


def db_differences(actual, expected, limit=10):
    """Short human-readable list of which records differ."""
    diffs = []
    for table in expected:
        for key in sorted(set(actual[table]) | set(expected[table])):
            a, e = actual[table].get(key), expected[table].get(key)
            if a == e:
                continue
            if a is None or e is None:
                diffs.append(f"{table}[{key}]: present in only one database")
                continue
            for field in sorted(set(a) | set(e)):
                if a.get(field) != e.get(field):
                    diffs.append(f"{table}[{key}].{field}: agent produced "
                                 f"{json.dumps(a.get(field))[:200]}, expected "
                                 f"{json.dumps(e.get(field))[:200]}")
    return diffs[:limit] + ([f"... and {len(diffs) - limit} more"] if len(diffs) > limit else [])


def conversation_text(log):
    """The conversation as τ²-bench's judge sees it: one "role: content" line per message.
    A turn where the agent only called tools has no text, which τ²-bench prints as None."""
    lines = []
    for m in log:
        if m["who"] in ("agent", "agent_tool_turn"):
            lines.append(f"assistant: {m['text']}")
        elif m["who"] == "user":
            lines.append(f"user: {m['text']}")
        elif m["who"] == "tool":
            lines.append(f"tool: {m['output']}")
    return "\n".join(lines)


def judge_nl_assertions(client, model, log, assertions, usage):
    prompt = (JUDGE_USER.replace("{{CONVERSATION}}", conversation_text(log))
              .replace("{{ASSERTIONS}}", str(assertions)))  # str() gives Python's list format, as upstream
    r = client.messages.create(
        model=model, max_tokens=16000, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        # effort "low" mirrors τ²-bench's judge setting (reasoning_effort="low")
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}})
    u = usage.setdefault("judge", {"input": 0, "output": 0})
    u["input"] += r.usage.input_tokens
    u["output"] += r.usage.output_tokens
    text = next(b.text for b in r.content if b.type == "text")
    return json.loads(text)["results"]


def grade(client, judge_model, task, final_db, fresh_db, log, ended_because, usage):
    """Returns a dict with two verdicts:
    code_passed - ended normally and database matches (no LLM involved)
    passed      - code_passed AND every judge check met: the official, τ²-bench verdict
    """
    criteria = task["evaluation_criteria"]
    judge_graded = "NL_ASSERTION" in criteria["reward_basis"] and bool(criteria.get("nl_assertions"))
    verdict = {"passed": False, "code_passed": False, "judge_graded": judge_graded,
               "ended_because": ended_because, "db_match": None, "db_diffs": [],
               "nl_results": None}
    if ended_because != "user_stop":
        verdict["reason"] = f"Conversation did not finish normally ({ended_because})."
        return verdict

    code_reasons, judge_reasons = [], []
    gold = expected_db(task, fresh_db)
    verdict["db_match"] = final_db == gold
    if "DB" in criteria["reward_basis"] and not verdict["db_match"]:
        verdict["db_diffs"] = db_differences(final_db, gold)
        code_reasons.append("Database does not match the expected end state.")

    if judge_graded:  # judged even if the database check failed, as upstream does
        results = judge_nl_assertions(client, judge_model, log, criteria["nl_assertions"], usage)
        verdict["nl_results"] = results
        failed = [r["expectedOutcome"] for r in results if not r["metExpectation"]]
        if failed:  # as upstream, an empty result list counts as all met
            judge_reasons.append("Judge says not met: " + "; ".join(failed))

    verdict["code_passed"] = not code_reasons
    verdict["passed"] = not code_reasons and not judge_reasons
    verdict["reason"] = " ".join(code_reasons + judge_reasons) or (
        "Database matches the expected end state"
        + (" and the judge says all checks were met." if judge_graded else "."))
    return verdict
