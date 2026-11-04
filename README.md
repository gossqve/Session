# Stateful AI Session Re-placement

Pure-software discrete-event simulation for a stateful LLM Session Re-placement research project.

## Current status

**S0 only**: one Edge, one Session, two or more Turns, fixed model, no mobility/migration/competition. Synthetic parameters are for hand-checkable functionality only, **not hardware profiling or paper results**.

The simulator records input upload, per-token Prefill/Decode work and KV growth, token-level wireless delivery, full Turn E2E, zero Idle between Turns, and final KV release. The global event queue uses deterministic tie-breaking.

Not yet implemented: GPU concurrent sharing and priority preemption, directed wired Max-Min, mobility, Check coordinator, live KV Copy / Shadow / Cutover, No-op/Greedy comparisons, Gymnasium/PPO.

## Run smoke case from repository root

Python 3.10+ and standard library are sufficient:

```bash
PYTHONPATH=src python3 -m replacement.cli --config configs/s0_smoke.json --out runs/s0_smoke
```

## Run automated tests

```bash
python3 -m unittest discover -s tests -v
```

## Expected S0 smoke metrics

- Two planned Turns, both fully delivered.
- Each Turn E2E = **0.7 s**, mean = **0.7 s**.
- Turn 2 submission = Turn 1 complete delivery time = **0.7 s**.
- Historical context after both Turns = **6 tokens**.
- Peak authority KV before natural session end = **24 bytes**, final authority KV = **0**.

The hand-calculation uses 2 input tokens x 1 Byte at 80 bit/s (0.2 s); Prefill 2 x 1 eq-work at 10 eq-work/s (0.2 s); Decode 1 x 2 eq-work at 10 eq-work/s (0.2 s); and one output token x 1 Byte at 80 bit/s (0.1 s).

S0 validates that the **whole planned workload** fits the Context Window and KV capacity. Runtime `ContextLimit`/`KVBlocked` handling is intentionally not yet implemented; this is a limited smoke case, not the full approved model.

## Outputs

The command writes `runs/s0_smoke/config.json`, `summary.json`, `turns.csv`, and `events.jsonl`. The `runs/` directory is Git-ignored. The workload plan is simulator-internal, not an online policy observation.

## Development approach

Expand the validated event simulator in stages S1 GPU -> S2 network -> S3 mobility -> S4 migration -> S5 baselines -> S6 complete features -> S7 PPO. Keep policy adapters separate from resource, KV, and network mechanics.
