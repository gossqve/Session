# S0–S2 reproduction and architecture

Python 3.10+, standard library. Run from repository root:

```powershell
python -m unittest discover -s tests -v
python scripts/verify_s2c.py
```

The second command executes exact Oracle comparisons, dynamic/shared Serving,
the full suite and earlier verifiers. It creates new `runs/s2c_*`, `runs/s2b_*`
and `runs/s1e_*` output directories. No prior run is required.

## Authoritative inputs

`configs/` holds synthetic experiment inputs. `tests/` includes the independent
rational vertex Oracle (`max_min_oracle.py`) and mathematical fixtures in Python.
`docs/s1d_verification.json` is a REQUIRED historical regression fixture read by
`scripts/verify_s1e.py`; its stored old run paths are provenance strings, never
directories that the verifier opens. Keep its contents and path stable.
All other stage verification JSON/logs are optional local history.

The current model is indexed by [model_spec/README.md](model_spec/README.md).
Original model Markdown is preserved; explicit user overrides exclude priorities,
preemption, old model selectors and per-Turn Access plans.

## Canonical modules and ownership

- `core/entities.py`: unique ModelSpec, SessionState, TurnState, EdgeState,
  immutable OutputToken. Model structure derives KV Byte/token.
- `core/runtime.py`: Turn transitions, explicit token_id delivery, Session end.
- `core/workload.py`: private future workload; `core/observation.py`: frozen
  whitelist values only, without Driver/Config/future-event references.
- `resources/`: unique GPU Equal-Share, FCFS Turn slots, typed compute and KV.
- `network/`: static Area/DirectedLink/FixedPath/NetworkTopology; Flow lifecycle,
  exact Fraction Byte accounting, default unweighted Max-Min progressive filling;
  WirelessRuntime uses the same Byte kernel with independent Session/direction rates.
- `simulation/events.py`: single event queue; `simulation/serving.py`: formal
  multi-Session/Turn executor; `simulation/s0.py`: retained lifecycle/safety fixture.
- `demos/` and `replacement.cli`: implemented CLI entry points, no root forwarding
  modules. All demo inputs are supplied from `configs/`.

GPU continuous Prefill/Decode retains one Turn slot; KVBlocked releases it and
keeps completed pending work. Context/KV commits are atomic and cumulative.
Network reallocation first settles old Byte, then changes activity/rates and
invalidates forecasts. One response Flow per Turn/path receives actual committed
Tokens. Full wired Token arrival precedes wireless FIFO. Only complete UE delivery
ends the Turn; the next Turn submits at the same time. Full E2E is receive minus
submit; incomplete all-planned means are null.

Topology-enabled Serving checks permitted Access/Execution membership, deployment
and both directed paths. Frozen Token origins never follow later position fields.
The default MaxMinAllocator accounts for all links on frozen flows' paths and
recovers residual capacity. DisjointPathAllocator is an explicit historical guard.
Wireless remains outside wired sharing. Units: eq-work/s, bit/s, Byte, seconds.

## Scripts and artifacts

`verify_s1e.py`, `verify_s2b.py`, `verify_s2c.py` are reproducible acceptance
drivers. `audit_s2c.py` runs the independent test-only Oracle; `stress_s2b.py`
executes deterministic conservation scenarios. Keep `tests/` when running these
scripts: the Oracle driver imports test utilities by design.

Simulation results include Flow/Link rate and utilization traces, G/Y Byte
progress, Token/Turn/Session records, GPU/KV records and offline config copies.
These are outputs under `runs/`; they are not test inputs or publishable source.

S3 actual Markov/Handover/Draining, S4 migration/Shadow/Cutover and later policies
are future work. No performance claim for real hardware or model weights is made.
