"""Summarize Inspect τ²-bench logs: per-task results, pass^1, pass^k, tokens and cost.

pass^k (τ-bench's measure): for each task, the chance that k randomly chosen
epochs ALL pass = C(c, k) / C(n, k), where n = epochs run and c = epochs passed.
Averaged over tasks. With k = n this is simply "did every epoch pass".
Usage: python inspect/summarize.py <log.eval> [k]
"""
import sys
from collections import defaultdict
from math import comb

from inspect_ai.log import read_eval_log

# $ per million tokens: input, output, cache write (5-min, 1.25x input), cache read (0.1x input)
PRICES = {
    "anthropic/claude-haiku-5-5": (0.10, 0.50),
    "anthropic/claude-sonnet-5-5": (2.00, 10.00),
}


def cost(model, u):
    i, o = PRICES[model]
    return (u.input_tokens * i + u.output_tokens * o
            + (u.input_tokens_cache_write or 0) * i * 1.25
            + (u.input_tokens_cache_read or 0) * i * 0.10) / 1e6


def main(path, k=None):
    log = read_eval_log(path)
    by_task = defaultdict(list)
    for s in log.samples:
        sc = next(iter(s.scores.values()))
        # "turns" = messages in the customer-side conversation (what the port records;
        # slim_log.py moves it to the store and shows the agent's view instead)
        turns = len(s.store.get("original_messages_customer_side", s.messages))
        by_task[str(s.id)].append((s.epoch, sc.value == "C", sc.explanation, turns))
    n = log.eval.config.epochs or 1
    k = int(k) if k else n
    print(f"Log: {path}\nTasks: {len(by_task)}  Epochs: {n}\n")
    print("task  epochs passed  turns  first failure reason")
    p1, pk = [], []
    for tid in sorted(by_task, key=int):
        rows = sorted(by_task[tid])
        c = sum(r[1] for r in rows)
        p1.append(c / len(rows))
        pk.append(comb(c, k) / comb(len(rows), k))
        fail = next((r[2] for r in rows if not r[1]), "")
        print(f"{tid:>4}  {c}/{len(rows)}  {','.join(str(r[3]) for r in rows):>10}  {(fail or '').splitlines()[0][:90] if fail else ''}")
    print(f"\npass^1 = {sum(p1)/len(p1):.2f}")
    if k > 1:
        print(f"pass^{k} = {sum(pk)/len(pk):.2f}")
    total = 0.0
    print("\nTokens and cost:")
    for model, u in log.stats.model_usage.items():
        c = cost(model, u)
        total += c
        print(f"  {model}: input {u.input_tokens:,}, cache write {u.input_tokens_cache_write or 0:,}, "
              f"cache read {u.input_tokens_cache_read or 0:,}, output {u.output_tokens:,} "
              f"(of which reasoning {u.reasoning_tokens or 0:,}) -> ${c:.3f}")
    print(f"  total: ${total:.3f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
