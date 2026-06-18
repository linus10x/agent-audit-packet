# Independent review record - agent-audit-packet

This packet wraps the proven `agent-funds-gate` control and makes its proof
forwardable, one-command runnable, and CI-gradable by a non-author reviewer.
It was built by one agent and reviewed by a different one (writer != reviewer),
adversarially and fail-closed, before any public release. Both the review and a
reproduced polarity proof are recorded here.

## Review 1 - adversarial pass (2026-06-18)
Verdict: **PASS** (no confirmed defects), with one LOW-severity hardening item.

The reviewer reproduced every check from a real clean clone
(`git clone ~/agent-audit-packet`), with no `pip install` and with sockets
disabled (zero network):

- **Clean-clone, zero-install, no-network repro.** `./verify.sh` (and
  `python3 -m audit_packet.verify`) exit 0: defeat-first line, governed DENY
  with the precise OFAC cite + `screen_completion_precedes_execution`, the
  second-line evidence table, ALL PASS. `evidence.json` correctly gitignored.
- **Polarity / falsifiability.** Stripping the ordering block in
  `vendor/agent_funds_gate/gate.py` drove the centerpiece test
  `test_under_governed_allows_and_governed_denies_the_race` RED
  (`AssertionError: assert 'ALLOW' == 'DENY'`); restore -> green. The test
  asserts the PRESENCE of the safe DENY, not the mere absence of an ALLOW.
- **No false-pass path.** `ProbeResult.outcome` is a derived `@property`
  (not settable; a fabricated PASS cannot be injected); `build_evidence([])`
  raises (no green on empty); forcing governed=ALLOW yields outcome=FAIL,
  `all_pass=False`, no PASS token rendered. The vendored gate DENYs every
  malformed / subject-mismatch / fall-through case and never raises.
- **Exit-code contract is a real gate.** regression -> 2, embedded test fail
  -> 3, vendor drift -> 4, empty -> 5, green -> 0; verified including the
  no-pytest degrade path (injected governed=ALLOW with pytest hidden still
  exits 2 and prints REGRESSION/FAIL).
- **Vendor integrity.** All four SHA-256 in `vendor/VENDOR.md` match the
  vendored files AND `agent-funds-gate` at pinned commit
  `19354ac0d086234eda3ace14383dadf1681431c5`. Editing a vendored file ->
  integrity test RED + driver exit 4; restore -> exit 0.
- **Evidence truthfulness.** The reg anchor and assertion are read OUT of the
  live `GateDecision` (`rule_cite`, `failing_assertion`), never re-typed.
- **Anti-clone.** `audit_packet` defines no `FundsGate` / `authorize` and no
  ordering comparison; it imports the real vendored surface. Wrapper, not a
  renamed control.
- **Firewall / framing.** Prose is firewall-clean and follows the framing law
  ("we attacked our own gate," never "caught a real incident").

LOW finding (non-blocking): the driver's exit-code MAPPING
(`{all_pass=False -> non-zero}`) was regression-tested only in
`test_verify.py`, which the embedded step-5 suite excludes to avoid pytest
re-entrancy. Escaping it required a double fault and the driver still printed
REGRESSION/FAIL (never ALL PASS), but the mapping a CI consumer trusts most was
not self-checked by `./verify.sh`.

## Fix applied (TDD: RED first) - commit 0fa0f51
The inline mapping was extracted into a pure function
`exit_code_for(report, suite_rc) -> int` in `verify.py`, and
`test_exit_code_mapping_is_self_checked` was added to `tests/test_evidence.py`
(an embedded-safe file the driver's step-5 suite runs), asserting green -> 0,
regressed `all_pass=False` -> 2 (and that 2 takes precedence under a failing
suite), and `green + suite_rc != 0` -> 3 - directly, without calling `main()`
(no re-entrancy). The 0/2/3/4/5 contract is unchanged; the re-entrancy guard is
untouched. Embedded suite 15 -> 16 passed; full suite 22 -> 23 passed.

## Review 2 - confirmation pass (2026-06-18)
Verdict: **CONFIRMED-FIXED.** Reproduced from a fresh clean clone, no install,
no network:
- `./verify.sh` exits 0; embedded suite 16 passed; full `pytest -q` 23 passed.
- The new test asserts the mapping directly, lives in `test_evidence.py`
  (in the embedded set; `test_verify.py` is not), and calls neither `main()`
  nor any subprocess.
- The end-to-end exit-code contract is unchanged: regression -> 2, embedded
  fail -> 3, vendor drift -> 4, empty -> 5, green -> 0. Stripping the ordering
  check exits 4 (integrity catches the vendored-file edit first - correct
  fail-closed layering) and prints ALL PASS zero times; restore -> exit 0.
- Re-entrancy guard intact (file-scope exclusion + `AUDIT_PACKET_EMBEDDED_RUN`
  env guard; exactly one embedded pytest run, no recursion).
The prior LOW finding is closed; no new findings.

## Polarity proof (reproduced)
The packet's central claim is falsifiable and asserts the PRESENCE of the safe
condition:

```
# strip the ordering-check block in vendor/agent_funds_gate/gate.py:
#   if screen.completed_seq is None or screen.completed_seq >= transfer_seq:
#       return self._deny(ORDERING_ASSERTION, screen, evidence)
python3 -m pytest -q tests/test_probes.py::test_under_governed_allows_and_governed_denies_the_race
# -> RED: AssertionError: assert 'ALLOW' == 'DENY'   (the race is allowed again)
# restore the block:
python3 -m pytest -q     # -> 23 passed
```

When the vendored file itself is edited (rather than monkeypatched), the
vendor-integrity check fires first and the driver returns 4 - the same defect
surfaced one layer earlier, also fail-closed.

## Status
Reviewer-passed (writer != reviewer) and polarity-proven. Release to public
GitHub stays news-pegged and owner-tap. Framing law: "we attacked our own gate,"
never "caught a real incident."
