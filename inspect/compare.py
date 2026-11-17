"""Compare two agent-prompt versions sample by sample, each from one or more Inspect logs.

Usage:
  python inspect/compare.py --a LOG [LOG ...] --b LOG [LOG ...] [--suspects train] [--names v0,v1]

--suspects <split> excludes that split's samples listed in inspect/suspect_samples.json
(expected answers we believe are wrong); --exclude 1,2,3 excludes ad-hoc ids instead.

Logs on one side are combined (e.g. a baseline split across two runs). Only samples present
on both sides are compared. pass^k as in summarize.py: per sample C(c,k)/C(n,k), averaged.
Also lists, for samples that passed under A in every epoch, any epoch that fails under B
(a regression, e.g. the agent now doing something it should have refused).
"""
import argparse
import json
import pathlib
from collections import defaultdict
from math import comb

from inspect_ai.log import read_eval_log


def results(paths):
    out = defaultdict(list)  # sample id -> [passed per epoch]
    for p in paths:
        log = read_eval_log(p)
        for s in log.samples:
            out[str(s.id)].append(next(iter(s.scores.values())).value == "C")
    return out


def stats(res, ids, k):
    p1 = sum(sum(res[i]) / len(res[i]) for i in ids) / len(ids)
    pk = sum(comb(sum(res[i]), k) / comb(len(res[i]), k) for i in ids) / len(ids)
    return p1, pk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--suspects", default="", help="split in inspect/suspect_samples.json: train or test")
    ap.add_argument("--names", default="A,B")
    args = ap.parse_args()
    na, nb = args.names.split(",")
    a, b = results(args.a), results(args.b)
    ids = sorted(set(a) & set(b), key=int)
    k = min(min(len(a[i]) for i in ids), min(len(b[i]) for i in ids))
    excl = {x for x in args.exclude.split(",") if x}
    if args.suspects:
        f = pathlib.Path(__file__).parent / "suspect_samples.json"
        excl |= set(json.loads(f.read_text())[args.suspects])

    print(f"{'sample':>6}  {na:>5}  {nb:>5}  change")
    for i in ids:
        ca, cb = sum(a[i]), sum(b[i])
        mark = "" if ca == cb else ("better" if cb > ca else "WORSE")
        print(f"{i:>6}  {ca}/{len(a[i])}    {cb}/{len(b[i])}    {mark}{'  (suspect)' if i in excl else ''}")

    for label, sel in [("all", ids), (f"excluding suspects {','.join(sorted(excl, key=int))}", [i for i in ids if i not in excl])]:
        if not sel or (label != "all" and not excl):
            continue
        a1, ak = stats(a, sel, k)
        b1, bk = stats(b, sel, k)
        print(f"\n{label} ({len(sel)} samples): pass^1 {na} {a1:.2f} -> {nb} {b1:.2f} ({b1 - a1:+.2f}); "
              f"pass^{k} {ak:.2f} -> {bk:.2f} ({bk - ak:+.2f})")

    reg = [i for i in ids if all(a[i]) and not all(b[i])]
    print(f"\nPassed every epoch under {na} but not under {nb}: {', '.join(reg) if reg else 'none'}")


if __name__ == "__main__":
    main()
