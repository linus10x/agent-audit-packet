"""Probe registry and the single v1 OFAC probe.

This module is a WRAPPER. It writes no gate logic: it imports the proven control
from the vendored ``agent_funds_gate`` and runs the documented race scenario
through both a governed gate and a naive-mode gate. The reg anchor and the
failing assertion in every result are read OUT of the real ``GateDecision`` and
are never re-typed as string literals here. The single source of truth is the
gate.

The probe's scenario is plain DATA (strings, ints, an enum value) passed into
``FundsGate.authorize(...)``. A fixture can never select a code path, name a
module to import, or trigger any write, network, or spend.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable

from agent_funds_gate import FundsGate, GateDecision, ScreenResult, ScreenStatus

# The documented race, reproduced verbatim from the upstream defeat-first story:
# a transfer fires at seq 10; the OFAC screen for the SAME party does not COMPLETE
# until seq 15, after the money moved. The screen is CLEAR and bound to the subject,
# so only the ORDERING check (enforced by the governed gate, stripped by naive_mode)
# stands between this scenario and an OFAC violation.
_SDN_VERSION = "2026-06-17"
_SUBJECT = "BLOCKED PERSON ALPHA"
_TRANSFER_SEQ = 10
_SCREEN_COMPLETED_SEQ = 15


class ProbeOutcome(enum.Enum):
    PASS = "pass"  # governed gate correctly DENYs the unsafe scenario (control holds)
    FAIL = "fail"  # governed gate ALLOWs the unsafe scenario (control regressed)


@dataclass(frozen=True)
class ProbeResult:
    """The verdict of one probe. ``outcome`` is DERIVED from the two real gate
    decisions, never set by a caller, so a regressed control can never read PASS.
    """

    probe_id: str
    control_name: str
    reg_anchor: str
    assertion: str
    governed_decision: GateDecision
    naive_decision: GateDecision

    @property
    def outcome(self) -> ProbeOutcome:
        # PASS iff the governed gate DENYs the race AND the naive gate ALLOWs it.
        if (
            self.governed_decision.decision == "DENY"
            and self.naive_decision.decision == "ALLOW"
        ):
            return ProbeOutcome.PASS
        return ProbeOutcome.FAIL


def ofac_screen_before_transfer_probe() -> ProbeResult:
    """Run the documented screen-completes-after-transfer race through both a
    governed and a naive-mode vendored gate, and report the result. The reg
    anchor and assertion are read out of the governed decision.
    """
    race_screen = ScreenResult(
        ScreenStatus.CLEAR,
        _SDN_VERSION,
        completed_seq=_SCREEN_COMPLETED_SEQ,
        subject=_SUBJECT,
    )

    governed = FundsGate(_SDN_VERSION).authorize(
        subject=_SUBJECT, transfer_seq=_TRANSFER_SEQ, screen=race_screen
    )
    naive = FundsGate(_SDN_VERSION, naive_mode=True).authorize(
        subject=_SUBJECT, transfer_seq=_TRANSFER_SEQ, screen=race_screen
    )

    return ProbeResult(
        probe_id="ofac_screen_before_transfer",
        control_name="OFAC screen-before-transfer gate",
        reg_anchor=governed.rule_cite or "",
        assertion=governed.failing_assertion or "",
        governed_decision=governed,
        naive_decision=naive,
    )


OFAC_PROBE = ofac_screen_before_transfer_probe

# v1 ships exactly one proven probe. ECOA / SR 11-7 are roadmap rows in
# CONTROL_INDEX.md, not here. Add a probe by appending its callable; everything
# downstream iterates the registry.
PROBE_REGISTRY: tuple[Callable[[], ProbeResult], ...] = (OFAC_PROBE,)


def run_all_probes() -> list[ProbeResult]:
    """Call every probe in registry order and return their results."""
    return [probe() for probe in PROBE_REGISTRY]
