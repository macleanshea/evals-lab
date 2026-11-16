"""Write a slimmed copy of an Inspect τ²-bench log, small enough for git and the viewer.

The port keeps the 3.3 MB airline database (and the "expected" database built by
the grader) in each sample's store, and records every change to it as store/state
events: ~3 MB per sample once zipped. This copy drops those database snapshots
and nothing else: conversations, agent tool calls and results, model calls,
scores and token usage are all kept.

It also makes the viewer's Messages tab readable. The port records the main
conversation from the customer simulator's side, so there the customer is
"assistant" and the agent is "user". After scoring (so scores are unaffected),
this swaps in the agent's own copy of the conversation, kept by the port in the
store: agent = "assistant", customer = "user", with the agent's tool calls and
results inline. The original customer-side messages stay in the store under
CUSTOMER_VIEW_KEY.
Usage: python inspect/slim_log.py <raw.eval> <out_dir>
"""
import pathlib
import sys

from inspect_ai.log import read_eval_log, read_eval_log_samples, write_eval_log
from inspect_ai.model import ChatMessage
from pydantic import TypeAdapter

AGENT_VIEW_KEY = "StoredAgentState:AirlineAgent:messages"
CUSTOMER_VIEW_KEY = "original_messages_customer_side"


def is_db(path_or_key: str) -> bool:
    return ":db" in path_or_key or "expected_db_" in path_or_key


def slim_sample(s):
    s.store = {k: v for k, v in s.store.items() if not is_db(k)}
    agent_view = s.store.get(AGENT_VIEW_KEY)
    if agent_view and CUSTOMER_VIEW_KEY not in s.store:
        s.store[CUSTOMER_VIEW_KEY] = [m.model_dump(mode="json") for m in s.messages]
        s.messages = TypeAdapter(list[ChatMessage]).validate_python(agent_view)
    kept = []
    for e in s.events:
        changes = getattr(e, "changes", None)
        if changes is not None:
            e.changes = [c for c in changes if not is_db(c.path)]
            if not e.changes:
                continue
        kept.append(e)
    s.events = kept
    return s


def main(raw, out_dir):
    # One sample at a time: a full 120-sample log does not fit in memory at once.
    log = read_eval_log(raw, header_only=True)
    log.samples = [slim_sample(s) for s in read_eval_log_samples(raw, all_samples_required=False)]
    out = pathlib.Path(out_dir) / pathlib.Path(raw).name
    write_eval_log(log, str(out))
    print(f"Slimmed {raw} -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
