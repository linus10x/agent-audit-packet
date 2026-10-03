# agent-audit-packet

A forwardable OFAC audit packet. Clone one repo, run one command, and get
reviewer-readable evidence that an under-governed payments agent FAILS a
regulated OFAC control and a governed agent PASSES it, with a CI-grade exit code.

This is a wrapper around the agent-funds-gate control
(`agent-funds-gate`, vendored under `vendor/`). It is not a new control and not a
generic agent framework. I tested the gate against the race it is meant to stop, and it denies it.

## The one command

```
./verify.sh
```

Equivalent, with the no-install path set as the wrapper sets it:

```
PYTHONPATH=src:vendor python3 -m audit_packet.verify
```

No install, no network, no `make`. The driver reads only its own vendored files.

## What you see

1. A defeat-first line: the under-governed agent (ordering check stripped)
   ALLOWs a $250,000 transfer at seq 10 whose OFAC screen does not complete until
   seq 15, after the money moved. The violating race ships.
2. The governed gate DENYs the same race, naming the OFAC reg cite and the failing
   assertion `screen_completion_precedes_execution`. Both are read out of the real
   gate decision, never re-typed.
3. A second-line evidence table (PROBE, CONTROL, REG ANCHOR, ASSERTION, RESULT),
   one row per probe, every cell derived from the actual gate decisions.
4. A final verdict line and a forwardable `evidence.json` artifact.

## Exit-code contract

A reviewer can wire `./verify.sh` straight into CI and treat any non-zero as
"the control does not hold here."

| code | meaning |
|---|---|
| 0 | every probe PASS and the embedded suite green (the control holds) |
| 2 | a probe regressed (the governed path ALLOWed an unsafe scenario) |
| 3 | an embedded test failed |
| 4 | vendored-gate integrity mismatch (the pinned digests drifted) |
| 5 | empty run / internal error |
| other non-zero | unhandled failure (fail closed; never exit 0 on a crash) |

## What it ADDS vs what it REUSES

REUSES (verbatim, vendored, unchanged): the `FundsGate` ordering enforcement and
its `naive_mode` defeat; `ScreenResult`, `ScreenStatus`, `GateDecision`, the
`OFAC_CITE` string, and the `screen_completion_precedes_execution` assertion. The
packet writes zero gate logic and imports the real public surface. See
`vendor/VENDOR.md` for the pinned commit and per-file digests.

ADDS: a CI-grade driver with a deterministic multi-code exit contract
and an embedded regression suite; a second-line evidence layer (a reviewer table
plus a forwardable `evidence.json`) structured as an independent-review function
would record it; a probe registry built for extension (ECOA and SR 11-7 are named
roadmap rows in `CONTROL_INDEX.md`), shipping exactly one proven probe in v1; and
a single-clone, zero-install, no-network packaging discipline with content-pinned
vendoring.

The split: `agent-funds-gate` proves the control; `agent-audit-packet` makes that
proof forwardable, runnable in one command by a non-author reviewer, and emits
evidence with a CI exit code.

## Scope limits

All scope limits of the vendored control stand. v1 ships one probe (the OFAC
screen-before-transfer race). No new control, no name or fuzzy matching, no
50%-rule, no license logic, no signed-screen verification. No network, no install
step, no `make`, no Docker, no LLM calls, no agent runtime, no dashboard, and no
publish, send, or spend step. The packet terminates at a human reviewer reading
stdout or the `evidence.json` artifact.

## How it stays honest

The PASS/FAIL token is derived from the real `GateDecision.decision` strings:
there is no code path that prints PASS without the governed decision being a real
DENY and the naive decision being a real ALLOW. An empty run fails closed
(it cannot render green). The vendored control is pinned by per-file SHA-256, so
silent drift turns the run RED. The full test suite, including the centerpiece
polarity test, runs with `python3 -m pytest -q`.

## License

MIT for the packet's own wrapper code (see `LICENSE`). The vendored control is
reused upstream IP under MIT; see `vendor/VENDOR.md`.
