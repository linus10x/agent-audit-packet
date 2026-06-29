"""CI-grade audit driver: run the probes, print the evidence, decide the exit code.

Run: ``python3 -m audit_packet.verify`` (or ``./verify.sh``).

The framing law in all output is "we attacked our own gate," never "caught a
real incident": the defeat is shown first (the under-governed agent ALLOWs the
race), the control second (the governed gate DENYs it).

Exit-code contract:
  0  every probe PASS and the embedded suite green (the control holds)
  2  a probe regressed (the governed path ALLOWed an unsafe scenario)
  3  an embedded test failed
  4  vendored-gate integrity mismatch (the pinned digests drifted)
  5  empty run / internal error
  any other non-zero  unhandled failure (fail closed; never exit 0 on a crash)
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

# No-install bootstrap: ensure the vendored control is importable even when the
# pyproject pythonpath is not read (a bare ``python3 -m audit_packet.verify`` on
# a fresh clone does not load pytest config). This is what keeps the packet
# zero-install and no-network -- the vendored gate resolves from the repo tree.
_VENDOR_PATH = Path(__file__).resolve().parent.parent.parent / "vendor"
if _VENDOR_PATH.is_dir() and str(_VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(_VENDOR_PATH))

from .evidence import build_evidence, render_json, render_table  # noqa: E402
from .probes import ProbeOutcome, run_all_probes  # noqa: E402

EXIT_OK = 0
EXIT_PROBE_REGRESSED = 2
EXIT_TEST_FAILED = 3
EXIT_VENDOR_DRIFT = 4
EXIT_INTERNAL = 5

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent.parent
_VENDOR_DIR = _REPO_ROOT / "vendor" / "agent_funds_gate"
_VENDOR_MD = _REPO_ROOT / "vendor" / "VENDOR.md"
_TESTS_DIR = _REPO_ROOT / "tests"
_VENDORED_FILES = ("__init__.py", "decision.py", "gate.py", "screening.py")

# The embedded regression suite runs the control-locking test files (probes,
# evidence, vendor integrity). It deliberately excludes the driver-level tests
# (test_verify.py), which themselves invoke main() -- running them in-process
# would recurse pytest sessions without bound. The control behavior the embedded
# gate must catch (a regressed gate, a faked PASS, a drifted vendor) is fully
# locked by these three files.
_EMBEDDED_TEST_FILES = (
    "test_probes.py",
    "test_evidence.py",
    "test_vendor_integrity.py",
)
# Re-entrancy guard: a belt-and-suspenders block against the driver's embedded
# pytest run re-triggering the driver (defence in depth alongside the file scope).
_REENTRY_ENV = "AUDIT_PACKET_EMBEDDED_RUN"


def exit_code_for(report, suite_rc: int) -> int:
    """Pure exit-code mapping -- the single piece of logic a CI consumer trusts.

    Kept as a standalone pure function (no I/O, no main()) so the embedded
    regression suite can assert it directly WITHOUT re-running the driver or
    re-entering pytest. ``main()`` calls this; the contract is unchanged:

      report.all_pass is False  -> 2 (a probe regressed; the governed path ALLOWed)
      suite_rc != 0             -> 3 (an embedded test failed)
      otherwise                 -> 0 (the control holds and the suite is green)

    Probe regression takes precedence over a suite failure: a regressed control
    is the more severe, fail-closed signal. (Vendor drift -> 4 and empty run -> 5
    are decided earlier in ``main()`` before this mapping is reached.)
    """
    if not report.all_pass:
        return EXIT_PROBE_REGRESSED
    if suite_rc != 0:
        return EXIT_TEST_FAILED
    return EXIT_OK


def _check_vendor_integrity() -> bool:
    """Recompute the SHA-256 of each vendored file and match VENDOR.md. Returns
    True if all digests match, False on any drift or missing record."""
    try:
        text = _VENDOR_MD.read_text()
    except OSError:
        return False
    for name in _VENDORED_FILES:
        m = re.search(
            rf"`agent_funds_gate/{re.escape(name)}`\s*\|\s*`([0-9a-f]{{64}})`", text
        )
        if not m:
            return False
        try:
            actual = hashlib.sha256((_VENDOR_DIR / name).read_bytes()).hexdigest()
        except OSError:
            return False
        if actual != m.group(1):
            return False
    return True


def _run_embedded_tests() -> int:
    """Run the packet's own probe test suite in-process as a regression guard.

    Per orchestrator refinement #2, this degrades gracefully if pytest is not
    installed: the core gate (probe run + evidence + exit code) is pure Python
    and needs no pytest, which is what keeps the packet zero-install and
    no-network. Returns 0 if the suite passed OR pytest is absent (the probe
    outcomes alone then decide the exit code); non-zero if a test failed.
    """
    if os.environ.get(_REENTRY_ENV):
        # Already inside an embedded run; do not recurse.
        return 0
    try:
        import pytest  # noqa: F401
    except ImportError:
        print(
            "[note] pytest not installed -- skipping the embedded regression suite; "
            "the exit code is decided on the probe outcomes alone."
        )
        return 0
    targets = [str(_TESTS_DIR / name) for name in _EMBEDDED_TEST_FILES]
    os.environ[_REENTRY_ENV] = "1"
    try:
        return int(pytest.main(["-q", *targets]))
    finally:
        os.environ.pop(_REENTRY_ENV, None)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        # 0. Pinned-vendor integrity. A drifted control invalidates the proof.
        if not _check_vendor_integrity():
            print(
                "VENDOR INTEGRITY FAILURE: the vendored gate does not match its "
                "pinned SHA-256 digests in vendor/VENDOR.md."
            )
            return EXIT_VENDOR_DRIFT

        # 1. Run the probes.
        results = run_all_probes()

        # 2. Build the evidence (fails closed on an empty run).
        report = build_evidence(results)

        # 3. Defeat-first narrative, then the table.
        ofac = results[0]
        print("agent-audit-packet -- we attacked our own gate and showed it holds.")
        print()
        print(
            "[defeat] The under-governed agent (ordering check stripped) returns "
            f"{ofac.naive_decision.decision} for a $250,000 transfer at seq 10 whose OFAC"
        )
        print(
            "         screen does not COMPLETE until seq 15 -- after the money moved. "
            "The OFAC-violating race ships."
        )
        print()
        print(
            "[control] The governed gate returns "
            f"{ofac.governed_decision.decision} on the same race."
        )
        print(f"          rule_cite:         {ofac.governed_decision.rule_cite}")
        print(
            f"          failing_assertion: {ofac.governed_decision.failing_assertion}"
        )
        print()
        print(render_table(report))
        print()

        # 4. Write the forwardable artifact (in-tree path, no network).
        artifact = Path.cwd() / "evidence.json"
        artifact.write_text(render_json(report))
        print(f"[artifact] wrote {artifact}")
        print()

        # Final verdict line.
        if report.all_pass:
            print("ALL PASS -- the control holds.")
        else:
            failed = [r.probe_id for r in results if r.outcome is ProbeOutcome.FAIL]
            print(f"REGRESSION -- the control does NOT hold for: {', '.join(failed)}")

        # 5. Embedded regression suite (degrades if pytest absent).
        test_rc = _run_embedded_tests()

        # 6. Decide the exit code (pure mapping; self-checked by the embedded suite).
        return exit_code_for(report, test_rc)
    except ValueError:
        # Empty run / internal evidence guard.
        print("INTERNAL: no probes produced a result; cannot render a verdict.")
        return EXIT_INTERNAL
    except Exception as exc:  # fail closed on any unhandled error
        print(f"INTERNAL ERROR: {exc!r}")
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
