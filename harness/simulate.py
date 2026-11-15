"""One trial = one conversation between the agent model and the customer simulator.

Flow (mirrors τ²-bench's turn-taking):
  1. The agent "says" a fixed greeting: "Hi! How can I help you today?"
  2. The customer simulator replies.
  3. The agent may call tools any number of times, then sends a text reply.
  4. Repeat 2-3 until the customer writes ###STOP###, ###TRANSFER### or
     ###OUT-OF-SCOPE###, or a safety limit is hit (200 steps, 10 tool errors).
"""

import textwrap

from harness.retail_tools import call_tool

GREETING = "Hi! How can I help you today?"
STOP_TOKENS = ("###STOP###", "###TRANSFER###", "###OUT-OF-SCOPE###")
MAX_STEPS = 200   # τ²-bench default; every message (agent, customer, tool) is one step
MAX_ERRORS = 10   # τ²-bench default; failed tool calls before we give up
MAX_TOKENS = 16000


def ask_model(client, model, system, messages, usage, role, tools=None):
    """One API call. Adds the tokens it used to `usage[role]`."""
    kwargs = {"tools": tools} if tools else {}
    response = client.messages.create(model=model, max_tokens=MAX_TOKENS,
                                      system=system, messages=messages, **kwargs)
    u = usage.setdefault(role, {"input": 0, "output": 0})
    u["input"] += (response.usage.input_tokens
                   + (response.usage.cache_read_input_tokens or 0)
                   + (response.usage.cache_creation_input_tokens or 0))
    u["output"] += response.usage.output_tokens
    return response


def text_of(response):
    return "".join(b.text for b in response.content if b.type == "text").strip()


def run_trial(client, task, db, agent_system, user_system, tools, cfg):
    """Play one conversation. Mutates `db`. Returns (log, ended_because, usage)."""
    log = [{"who": "agent", "text": GREETING}]
    usage = {}
    agent_msgs = []                                     # the agent's view
    user_msgs = [{"role": "user", "content": GREETING}]  # the customer's view (roles flipped)
    steps, errors = 1, 0

    while True:
        # ---- customer turn
        r = ask_model(client, cfg["user_model"], user_system, user_msgs, usage, "user_sim")
        if r.stop_reason == "refusal":
            return log, "user_sim_refused", usage
        said = text_of(r) or "(empty message)"
        user_msgs.append({"role": "assistant", "content": r.content})
        log.append({"who": "user", "text": said})
        steps += 1
        if any(tok in said for tok in STOP_TOKENS):
            return log, "user_stop", usage
        agent_msgs.append({"role": "user", "content": said})

        # ---- agent turn: tool calls until it replies with text only
        while True:
            if steps >= MAX_STEPS:
                return log, "max_steps", usage
            r = ask_model(client, cfg["agent_model"], agent_system, agent_msgs, usage,
                          "agent", tools)
            if r.stop_reason == "refusal":
                return log, "agent_refused", usage
            agent_msgs.append({"role": "assistant", "content": r.content})
            steps += 1
            calls = [b for b in r.content if b.type == "tool_use"]
            if not calls:
                break
            # A tool-calling turn. Any text sent with it never reaches the customer.
            log.append({"who": "agent_tool_turn", "text": text_of(r) or None})
            results = []
            for call in calls:
                output, is_error = call_tool(db, call.name, call.input)
                errors += is_error
                log.append({"who": "tool", "name": call.name, "args": call.input,
                            "output": output, "error": is_error})
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": output, "is_error": is_error})
            agent_msgs.append({"role": "user", "content": results})
            steps += 1
            if errors >= MAX_ERRORS:
                return log, "too_many_tool_errors", usage

        reply = text_of(r) or "(empty message)"
        log.append({"who": "agent", "text": reply})
        user_msgs.append({"role": "user", "content": reply})
        if steps >= MAX_STEPS:
            return log, "max_steps", usage


def scenario_text(task):
    """The customer's hidden script, laid out exactly as τ²-bench renders it."""
    ins = task["user_scenario"]["instructions"]
    tab = lambda s: textwrap.indent(s, "\t")
    lines = [f"Domain: {ins['domain']}", f"Reason for call:\n{tab(ins['reason_for_call'])}"]
    if ins.get("known_info") is not None:
        lines.append(f"Known info:\n{tab(ins['known_info'])}")
    if ins.get("unknown_info") is not None:
        lines.append(f"Unknown info:\n{tab(ins['unknown_info'])}")
    lines.append(f"Task instructions:\n{tab(ins['task_instructions'])}")
    out = []
    if task["user_scenario"].get("persona"):
        out += ["Persona:", tab(task["user_scenario"]["persona"])]
    out += ["Instructions:", tab("\n".join(lines))]
    return "\n".join(out)
