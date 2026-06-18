# Control index

One row per probe: probe id, the control it exercises, the reg anchor, and its
status. v1 ships exactly one proven probe. The roadmap rows are named but not
built; they do not appear in `PROBE_REGISTRY` and are not asserted by any test.

| probe id | control | reg anchor | status |
|---|---|---|---|
| `ofac_screen_before_transfer` | OFAC screen-before-transfer gate (screen must COMPLETE before the transfer executes) | 31 CFR 501.603 / 501.604; strict liability under IEEPA, 50 U.S.C. 1705 | SHIPPED (v1) |
| `ecoa_adverse_action` | ECOA adverse-action reason gate | ECOA / Reg B (roadmap) | ROADMAP (not built) |
| `model_risk_validation` | SR 11-7 model validation gate | SR 11-7 (roadmap) | ROADMAP (not built) |

Extension contract: add a probe by appending its callable to `PROBE_REGISTRY` in
`src/audit_packet/probes.py`. Everything downstream iterates the registry, so the
driver, the evidence table, and the JSON artifact pick it up with no other change.
The reg anchor and the failing assertion for every probe are read out of the real
`GateDecision`; they are never re-typed in the index or the code.
