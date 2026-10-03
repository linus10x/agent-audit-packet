"""Reviewer-readable evidence for a second-line review.

Turns probe results into a reviewer-readable plain-ASCII table and a forwardable
machine-readable JSON artifact. Every cell is read from a ``ProbeResult``; the
PASS/FAIL token is a render of ``ProbeResult.outcome``, which is itself derived
from the two real ``GateDecision`` strings. There is no code path that prints
PASS without the governed decision being a real DENY and the naive decision being
a real ALLOW.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .probes import ProbeOutcome, ProbeResult

SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class EvidenceReport:
    rows: tuple[ProbeResult, ...]
    all_pass: bool


def build_evidence(results: list[ProbeResult]) -> EvidenceReport:
    """Compute the report from the actual outcomes. Fails closed (ValueError) on
    an empty result set so an empty run can never render as a green report.
    """
    if not results:
        raise ValueError(
            "build_evidence called with no probe results -- an empty run cannot "
            "render green; fail closed."
        )
    all_pass = all(r.outcome is ProbeOutcome.PASS for r in results)
    return EvidenceReport(rows=tuple(results), all_pass=all_pass)


def _result_token(row: ProbeResult) -> str:
    return "PASS" if row.outcome is ProbeOutcome.PASS else "FAIL"


def render_table(report: EvidenceReport) -> str:
    """Reviewer-readable plain-ASCII evidence table. One row per probe."""
    lines = []
    lines.append(
        "Second-line evidence (independent-review record) -- derived from the gate decisions:"
    )
    header = "PROBE | CONTROL | REG ANCHOR | ASSERTION | RESULT"
    lines.append(header)
    lines.append("-" * len(header))
    for row in report.rows:
        lines.append(
            " | ".join(
                (
                    row.probe_id,
                    row.control_name,
                    row.reg_anchor,
                    row.assertion,
                    _result_token(row),
                )
            )
        )
    return "\n".join(lines)


def _decision_to_dict(decision) -> dict:
    return asdict(decision)


def render_json(report: EvidenceReport) -> str:
    """Machine-readable evidence artifact mirroring the table exactly."""
    probes = []
    for row in report.rows:
        probes.append(
            {
                "probe_id": row.probe_id,
                "control_name": row.control_name,
                "reg_anchor": row.reg_anchor,
                "assertion": row.assertion,
                "governed_decision": _decision_to_dict(row.governed_decision),
                "naive_decision": _decision_to_dict(row.naive_decision),
                "outcome": row.outcome.value,
            }
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "all_pass": report.all_pass,
        "probes": probes,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
