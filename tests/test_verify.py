"""Driver exit-code contract + output ordering."""

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from audit_packet import verify as verify_mod
from audit_packet.probes import OFAC_PROBE, ProbeResult

from dataclasses import replace

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_driver_exits_zero_when_control_holds(capsys):
    # 3.12 green path returns 0.
    rc = verify_mod.main([])
    assert rc == 0


def test_driver_exits_nonzero_when_governed_path_allows(monkeypatch, capsys):
    # 3.13 REGRESSION fail-closed: a governed ALLOW must yield code 2 and print FAIL.
    def regressed_probe():
        good = OFAC_PROBE()
        regressed_governed = replace(
            good.governed_decision,
            decision="ALLOW",
            rule_cite=None,
            failing_assertion=None,
        )
        return ProbeResult(
            probe_id=good.probe_id,
            control_name=good.control_name,
            reg_anchor=good.reg_anchor,
            assertion=good.assertion,
            governed_decision=regressed_governed,
            naive_decision=good.naive_decision,
        )

    monkeypatch.setattr(verify_mod, "run_all_probes", lambda: [regressed_probe()])
    rc = verify_mod.main([])
    out = capsys.readouterr().out
    assert rc == 2
    assert "FAIL" in out


def test_driver_exits_nonzero_when_a_test_fails(monkeypatch):
    # 3.14 the embedded suite is a real gate: a test failure yields code 3.
    monkeypatch.setattr(verify_mod, "_run_embedded_tests", lambda: 1)
    rc = verify_mod.main([])
    assert rc == 3


def test_driver_prints_defeat_first_then_table(capsys):
    # 3.15 the defeat line precedes the evidence table.
    verify_mod.main([])
    out = capsys.readouterr().out
    defeat_idx = out.find("ALLOW")
    table_idx = out.find("REG ANCHOR")
    assert defeat_idx != -1
    assert table_idx != -1
    assert defeat_idx < table_idx


def test_driver_writes_evidence_json_artifact(tmp_path, monkeypatch):
    # 3.16 ./evidence.json is written, parses, all_pass matches the run.
    monkeypatch.chdir(tmp_path)
    rc = verify_mod.main([])
    artifact = tmp_path / "evidence.json"
    assert artifact.exists()
    parsed = json.loads(artifact.read_text())
    assert parsed["all_pass"] is (rc == 0)
    assert parsed["all_pass"] is True


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash unavailable")
def test_verify_sh_forwards_exit_code(tmp_path):
    # 3.17 the one-liner forwards the module exit code, end to end.
    proc = subprocess.run(
        ["bash", str(REPO_ROOT / "verify.sh")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 0
    assert "ALL PASS" in proc.stdout


def test_no_install_no_network_clone_to_green(tmp_path):
    # 3.18 LIVE-E2E acceptance: copy the repo, run with no install and no network.
    clone = tmp_path / "clone"
    shutil.copytree(
        REPO_ROOT,
        clone,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".git"),
    )
    # Disable the network by pointing at a sitecustomize that breaks sockets,
    # without installing anything. We assert exit 0 from a bare python3 -m run.
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{clone / 'src'}{os.pathsep}{clone / 'vendor'}"
    # Disable the network without breaking the socket type: any attempt to OPEN a
    # connection raises. The packet must reach ALL PASS with no install and no
    # outbound connection. We run the driver module directly via -m.
    boot = (
        "import socket\n"
        "socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw("
        "OSError('network disabled for no-network acceptance test'))\n"
        "socket.create_connection = lambda *a, **k: (_ for _ in ()).throw("
        "OSError('network disabled for no-network acceptance test'))\n"
        "import runpy\n"
        "runpy.run_module('audit_packet.verify', run_name='__main__')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", boot],
        capture_output=True,
        text=True,
        cwd=clone,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ALL PASS" in proc.stdout
