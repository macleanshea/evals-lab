"""Grader: decides PASS/FAIL for one trial, mirroring τ²-bench's retail rules.

A trial passes only if ALL of these hold:
  1. The conversation ended normally (the customer sent a stop token).
  2. Database check: the database after the conversation is identical to the
     database you get by applying the task's "gold" actions to a fresh copy.
  3. Natural-language assertions (only some tasks have them): an LLM judge
     reads the conversation and confirms every assertion was met.
"""

import json

from harness.retail_tools import call_tool

# Copied from τ²-bench's evaluator_nl_assertions.py so the judge gets the same instructions.
JUDGE_SYSTEM = """
        TASK
        - You will be given a list of expected outcomes and a conversation that was collected during a test case run.
        - The conversation is between an agent and a customer.
        - Your job is to evaluate whether the agent satisfies each of the expected outcomes.
        - Grade each expected outcome individually.

        FORMAT
        - Your response should be a JSON object with the following fields:
        - `reasoning`: a short explanation for your classification
        - `metExpectation`: `true` if the agent satisfies the expected outcomes, `false` otherwise
        - `expectedOutcome`: repeat the expectation from the input that you are grading

        Example response structure:
        {
            "results": [
                {
                    "expectedOutcome": "<one of the expected outcomes from the input>",
                    "reasoning": "<reasoning trace>",
                    "metExpectation": <false or true>,
                }
            ]
        }
        """

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


def judge_nl_assertions(client, model, log, assertions, usage):
    lines = []
    for m in log:
        if m["who"] in ("agent", "agent_aside"):
            lines.append(f"assistant: {m['text']}")
        elif m["who"] == "user":
            lines.append(f"user: {m['text']}")
        elif m["who"] == "tool":
            lines.append(f"tool: {m['output']}")
    prompt = f"""
        conversation:
        {chr(10).join(lines)}

        expectedOutcomes:
        {assertions}
        """
    r = client.messages.create(
        model=model, max_tokens=16000, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}})
    u = usage.setdefault("judge", {"input": 0, "output": 0})
    u["input"] += r.usage.input_tokens
    u["output"] += r.usage.output_tokens
    text = next(b.text for b in r.content if b.type == "text")
    return json.loads(text)["results"]


def grade(client, judge_model, task, final_db, fresh_db, log, ended_because, usage):
    """Returns a dict: passed (bool), reason (str), plus details for the transcript."""
    verdict = {"passed": False, "ended_because": ended_because,
               "db_match": None, "db_diffs": [], "nl_results": None}
    if ended_because != "user_stop":
        verdict["reason"] = f"Conversation did not finish normally ({ended_because})."
        return verdict

    criteria = task["evaluation_criteria"]
    basis = criteria["reward_basis"]
    reasons = []

    gold = expected_db(task, fresh_db)
    verdict["db_match"] = final_db == gold
    if "DB" in basis and not verdict["db_match"]:
        verdict["db_diffs"] = db_differences(final_db, gold)
        reasons.append("Database does not match the expected end state.")

    if "NL_ASSERTION" in basis and criteria.get("nl_assertions"):
        results = judge_nl_assertions(client, judge_model, log, criteria["nl_assertions"], usage)
        verdict["nl_results"] = results
        failed = [r["expectedOutcome"] for r in results if not r["metExpectation"]]
        if failed:
            reasons.append("Judge says these were not met: " + "; ".join(failed))

    verdict["passed"] = not reasons
    verdict["reason"] = " ".join(reasons) or (
        "Database matches the expected end state"
        + (" and all assertions were met." if verdict["nl_results"] else "."))
    return verdict
