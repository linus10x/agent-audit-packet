"""Evidence is truthful, derived from the gate, and fails closed on a lie."""

import json
import socket

import pytest

from audit_packet.evidence import (
    EvidenceReport,
    build_evidence,
    render_json,
    render_table,
)
from audit_packet.probes import OFAC_PROBE, ProbeOutcome, ProbeResult, run_all_probes

from dataclasses import replace


def _report():
    return build_evidence(run_all_probes())


def test_evidence_row_names_control_reg_anchor_assertion_and_result():
    # 3.5 the rendered table names control + reg anchor + assertion + PASS, one row.
    report = _report()
    table = render_table(report)
    row = OFAC_PROBE()
    assert row.control_name in table
    assert row.reg_anchor in table
    assert "screen_completion_precedes_execution" in table
    assert "PASS" in table


def test_reg_anchor_is_derived_from_gate_not_hardcoded():
    # 3.6 the cite is read out of the decision, not re-typed.
    from agent_funds_gate import OFAC_CITE

    result = OFAC_PROBE()
    assert result.reg_anchor == result.governed_decision.rule_cite
    assert result.reg_anchor == OFAC_CITE


def test_evidence_pass_cannot_be_faked_when_probe_allowed():
    # 3.7 FAIL-CLOSED anti-lie: a regressed governed ALLOW must render FAIL.
    good = OFAC_PROBE()
    regressed_governed = replace(
        good.governed_decision, decision="ALLOW", rule_cite=None, failing_assertion=None
    )
    regressed = ProbeResult(
        probe_id=good.probe_id,
        control_name=good.control_name,
        reg_anchor=good.reg_anchor,
        assertion=good.assertion,
        governed_decision=regressed_governed,
        naive_decision=good.naive_decision,
    )
    assert regressed.outcome is ProbeOutcome.FAIL

    report = build_evidence([regressed])
    assert report.all_pass is False
    table = render_table(report)
    assert "FAIL" in table
    assert "PASS" not in table
    parsed = json.loads(render_json(report))
    assert parsed["all_pass"] is False
    assert parsed["probes"][0]["outcome"] == "fail"


def test_render_json_matches_table_outcomes():
    # 3.8 table and JSON share one source.
    report = _report()
    parsed = json.loads(render_json(report))
    assert parsed["all_pass"] == report.all_pass
    assert parsed["probes"][0]["outcome"] == "pass"
    assert "PASS" in render_table(report)


def test_build_evidence_empty_results_fails_closed():
    # 3.9 an empty run can never render green.
    with pytest.raises(ValueError):
        build_evidence([])


def test_json_schema_has_required_fields():
    # 3.10 schema completeness.
    report = _report()
    parsed = json.loads(render_json(report))
    assert "all_pass" in parsed
    assert "schema_version" in parsed
    probe = parsed["probes"][0]
    for field in (
        "probe_id",
        "control_name",
        "reg_anchor",
        "assertion",
        "governed_decision",
        "naive_decision",
        "outcome",
    ):
        assert field in probe


def test_exit_code_mapping_is_self_checked():
    # 3.23 the driver's exit-code MAPPING -- the single piece of logic a CI
    # consumer trusts most -- is self-checked by the EMBEDDED suite (this file is
    # one of the three the driver's step-5 run executes), so ./verify.sh proves
    # its own contract without pytest re-entrancy. exit_code_for is a PURE
    # function asserted directly: no main() call, no driver run, no recursion.
    from audit_packet.verify import (
        EXIT_OK,
        EXIT_PROBE_REGRESSED,
        EXIT_TEST_FAILED,
        exit_code_for,
    )

    green = build_evidence(run_all_probes())
    assert green.all_pass is True
    # green report, embedded suite green -> 0
    assert exit_code_for(green, 0) == EXIT_OK

    # a regressed report (governed ALLOW) -> 2 (non-zero), regardless of suite_rc
    good = OFAC_PROBE()
    regressed_governed = replace(
        good.governed_decision, decision="ALLOW", rule_cite=None, failing_assertion=None
    )
    regressed_row = ProbeResult(
        probe_id=good.probe_id,
        control_name=good.control_name,
        reg_anchor=good.reg_anchor,
        assertion=good.assertion,
        governed_decision=regressed_governed,
        naive_decision=good.naive_decision,
    )
    regressed = build_evidence([regressed_row])
    assert regressed.all_pass is False
    assert exit_code_for(regressed, 0) == EXIT_PROBE_REGRESSED
    assert exit_code_for(regressed, 0) != EXIT_OK
    # probe regression takes precedence over a suite failure too
    assert exit_code_for(regressed, 1) == EXIT_PROBE_REGRESSED

    # green report but a FAILED embedded suite -> 3
    assert exit_code_for(green, 1) == EXIT_TEST_FAILED
    assert exit_code_for(green, 1) != EXIT_OK


def test_fixture_is_data_not_instructions(monkeypatch):
    # 3.11 INJECTION: the probe is pure data-in, no writes, no network, no eval.
    real_open = open

    def _no_write_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError(f"probe attempted a file write: {file!r} mode={mode!r}")
        return real_open(file, mode, *args, **kwargs)

    def _no_socket(*args, **kwargs):
        raise AssertionError("probe attempted a network socket")

    monkeypatch.setattr("builtins.open", _no_write_open)
    monkeypatch.setattr(socket, "socket", _no_socket)

    result = OFAC_PROBE()
    assert result.outcome is ProbeOutcome.PASS

    # The probe module imports only the vendored gate + stdlib (no eval/exec path).
    import audit_packet.probes as probes_mod
    src = open(probes_mod.__file__).read()
    assert "eval(" not in src
    assert "exec(" not in src
    assert "__import__" not in src
