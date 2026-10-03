"""Vendored-gate pinning: content digests, provenance, real-surface reuse, anti-clone."""

import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "agent_funds_gate"
VENDOR_MD = REPO_ROOT / "vendor" / "VENDOR.md"
PINNED_COMMIT = "1441a7c00ecb333f525a56d9ac9b54d6416e2b6a"
VENDORED_FILES = ("__init__.py", "decision.py", "gate.py", "screening.py")


def _recorded_digests():
    text = VENDOR_MD.read_text()
    digests = {}
    for name in VENDORED_FILES:
        m = re.search(rf"`agent_funds_gate/{re.escape(name)}`\s*\|\s*`([0-9a-f]{{64}})`", text)
        assert m, f"no recorded digest for {name} in VENDOR.md"
        digests[name] = m.group(1)
    return digests


def test_vendored_gate_matches_pinned_digests():
    # 3.19 DRIFT fail-closed: recompute each file's SHA-256 and match VENDOR.md.
    recorded = _recorded_digests()
    for name in VENDORED_FILES:
        actual = hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest()
        assert actual == recorded[name], f"vendored {name} drifted from pinned digest"


def test_vendor_md_records_upstream_and_commit():
    # 3.20 provenance: upstream named, full pinned SHA, reused MIT IP.
    text = VENDOR_MD.read_text()
    assert "agent-funds-gate" in text
    assert PINNED_COMMIT in text
    assert "MIT" in text
    assert "reused upstream IP" in text


def test_packet_imports_real_gate_surface():
    # 3.21 reuse, not re-implementation: the real surface imports and runs.
    from agent_funds_gate import (
        FundsGate,
        GateDecision,
        OFAC_CITE,
        ScreenResult,
        ScreenStatus,
    )

    assert isinstance(OFAC_CITE, str) and OFAC_CITE
    screen = ScreenResult(ScreenStatus.CLEAR, "2026-06-17", completed_seq=15, subject="X")
    decision = FundsGate("2026-06-17").authorize(
        subject="X", transfer_seq=10, screen=screen
    )
    assert isinstance(decision, GateDecision)


def test_packet_defines_no_gate_logic():
    # 3.22 anti-clone (per orchestrator refinement #1): the packet is a wrapper.
    # (a) audit_packet defines no class FundsGate and no def authorize anywhere.
    src_dir = REPO_ROOT / "src" / "audit_packet"
    for py in src_dir.rglob("*.py"):
        text = py.read_text()
        assert not re.search(r"class\s+FundsGate\b", text), f"{py} defines FundsGate"
        assert not re.search(r"def\s+authorize\b", text), f"{py} defines authorize"

    probes_text = (src_dir / "probes.py").read_text()
    # (b) probes.py imports FundsGate from the vendored control.
    assert re.search(
        r"from\s+agent_funds_gate\s+import\b.*FundsGate", probes_text
    ), "probes.py must import FundsGate from agent_funds_gate"
    # (c) the ordering COMPARISON of completed_seq appears nowhere in the packet.
    # Constructing ScreenResult(..., completed_seq=15) is allowed; comparing is not.
    for py in src_dir.rglob("*.py"):
        text = py.read_text()
        assert not re.search(r"completed_seq\s*(>=|<=|>|<|==|!=)", text), (
            f"{py} compares completed_seq -- ordering logic must live only in the gate"
        )
        assert not re.search(r"(>=|<=|>|<|==|!=)\s*completed_seq", text), (
            f"{py} compares completed_seq -- ordering logic must live only in the gate"
        )
