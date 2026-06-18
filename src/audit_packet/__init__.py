"""agent-audit-packet: a forwardable, one-command OFAC audit packet.

A go-to-market wrapper around the proven, vendored ``agent_funds_gate`` control.
It writes no gate logic: it runs the documented screen-completes-after-transfer
race through both a governed and an under-governed gate, and emits
independent-review-grade evidence with a CI-grade exit code.
"""

from .evidence import EvidenceReport, build_evidence, render_json, render_table
from .probes import (
    OFAC_PROBE,
    PROBE_REGISTRY,
    ProbeOutcome,
    ProbeResult,
    ofac_screen_before_transfer_probe,
    run_all_probes,
)

__all__ = [
    "run_all_probes",
    "ProbeResult",
    "ProbeOutcome",
    "OFAC_PROBE",
    "PROBE_REGISTRY",
    "ofac_screen_before_transfer_probe",
    "build_evidence",
    "EvidenceReport",
    "render_table",
    "render_json",
]
