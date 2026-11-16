"""Write a slimmed copy of an Inspect τ²-bench log, small enough for git and the viewer.

The port keeps the 3.3 MB airline database (and the "expected" database built by
the grader) in each sample's store, and records every change to it as store/state
events: ~3 MB per sample once zipped. This copy drops those database snapshots
and nothing else: conversations, agent tool calls and results, model calls,
scores and token usage are all kept.
Usage: python inspect/slim_log.py <raw.eval> <out_dir>
"""
import pathlib
import sys

from inspect_ai.log import read_eval_log, write_eval_log


def is_db(path_or_key: str) -> bool:
    return ":db" in path_or_key or "expected_db_" in path_or_key


def main(raw, out_dir):
    log = read_eval_log(raw)
    for s in log.samples or []:
        s.store = {k: v for k, v in s.store.items() if not is_db(k)}
        kept = []
        for e in s.events:
            changes = getattr(e, "changes", None)
            if changes is not None:
                e.changes = [c for c in changes if not is_db(c.path)]
                if not e.changes:
                    continue
            kept.append(e)
        s.events = kept
    out = pathlib.Path(out_dir) / pathlib.Path(raw).name
    write_eval_log(log, str(out))
    print(f"Slimmed {raw} -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
