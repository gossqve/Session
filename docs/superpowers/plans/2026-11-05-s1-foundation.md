# S1-Foundation implementation plan

Authority: integrated Section III + user's Foundation task + 开发建模注意.md
(2026-11-05). Direct Windows local edits only, Python 3.10 standard library.
No SSH, Git mutations, full KV recovery or multi-Session E2E.

Architecture: immutable structural ModelSpec; runtime Session/Turn entities;
Edge owns the existing GPUQueue through a typed compute registry. Resident KV,
running tasks and FCFS views are derived from their existing authoritative state.
Private workload driver reveals only current inputs and generation termination.
Explicit frozen observation DTOs copy only whitelisted scalar/tuple values.
S0 uses these entities and existing GPU completion events for each compute unit.

Migration: config.model -> ModelSpec; config.session -> SessionState;
old planned output_tokens -> private TurnPlan; old S0 TurnState -> runtime
TurnState; string GPU IDs -> typed GPUComputeTask registry; future workload
preflight -> actual Token commit checks. Existing H/L schema is removed.

- [x] Write RED tests for entities, binding/deployment, typed GPU ownership,
  future-invariant observation serialization and S0 runtime constraints.
- [x] Implement entities.py, workload.py, compute.py and observation.py.
- [x] Adapt S0/config/CLI compatibility to formal entities and runtime checks;
  preserve normal numerical results. Retain both old safety tests with runtime
  assertions (KV block; Context abnormal termination), not constructor preflight.
- [x] Audit Session priority removal and observation fields; keep original
  source-model documents unchanged with explicit latest overrides.
- [x] Run full regressions and S0/S1-A/S1-B demos; save output, review and
  produce docs/S1-Foundation_建模与实现对应报告.md plus upload manifest.

Boundary: minimal KV-blocked commit interface retains computed unit and legal
KV without automatic recovery. Context-limit turns never count as successful;
already generated responses drain before abnormal session cleanup. S1-C adds
full commit/retry lifecycle; S1-D adds complete multi-Session E2E.

Verification: Windows Python 3.10.9; 62/62 tests passed (7 S0, 17 S1-A,
19 S1-B, 19 Foundation). Two S0 safety cases retained and revised to actual
runtime checks. S0 smoke metrics unchanged; both GPU demos run. Raw output and
CLI summaries in docs/foundation_test_output.txt and foundation_verification.json.

Independent review: two P2 issues reproduced (same-ID alternate ModelSpec and
GPU Ready before Turn submission/current runtime). Both fixed with RED→GREEN
regressions; canonical model registry made read-only and binding clock checked
before scheduler mutation. No deferred review findings. Additional self-review
test fixed stale GPU progress in observations at interleaved downlink events.
