"""Probe registry + the centerpiece polarity behavior.

The centerpiece (3.1) asserts the PRESENCE of the safe DENY (governed mode) AND
the under-governed ALLOW, not merely the absence of an unsafe state.
"""

from dataclasses import replace

from audit_packet.probes import (
    OFAC_PROBE,
    PROBE_REGISTRY,
    ProbeOutcome,
    ProbeResult,
    ofac_screen_before_transfer_probe,
    run_all_probes,
)


def test_under_governed_allows_and_governed_denies_the_race():
    # 3.1 CENTERPIECE polarity. The under-governed agent ships the OFAC-violating
    # race (ALLOW); the governed control holds (DENY); the probe reads PASS.
    result = OFAC_PROBE()
    assert result.naive_decision.decision == "ALLOW"
    assert result.governed_decision.decision == "DENY"
    assert result.outcome is ProbeOutcome.PASS


def test_governed_deny_is_on_ordering_assertion():
    # 3.2 the DENY must be for the race reason, not an unrelated DENY.
    result = OFAC_PROBE()
    assert (
        result.governed_decision.failing_assertion
        == "screen_completion_precedes_execution"
    )


def test_probe_outcome_pass_requires_both_polarities():
    # 3.3 lock the FAIL polarity: a regressed governed ALLOW can never read PASS.
    good = OFAC_PROBE()
    assert good.outcome is ProbeOutcome.PASS

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


def test_registry_holds_exactly_one_probe_v1():
    # 3.4 guard against fabricated unbuilt probes.
    assert len(PROBE_REGISTRY) == 1
    assert PROBE_REGISTRY[0] is OFAC_PROBE
    assert OFAC_PROBE is ofac_screen_before_transfer_probe
    results = run_all_probes()
    assert len(results) == 1
