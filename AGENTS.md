# Rules for Codex / coding agents

Project: **Stateful AI Session Re-placement**, latest model dated 2026-11-02/03.

1. Read the authoritative model files in `docs/model_spec/` when they are available. Prefer the user's latest integrated Section III when conflicts occur; document unresolved ambiguities rather than changing the model.
2. Implement only the explicitly requested development stage. Current implemented scope: **S0 single Edge, single Session, deterministic synthetic workload, zero Idle**.
3. Keep simulator/environment mechanics separate from policies. Never let future session turns, future access changes, actual remaining outputs or future events leak into policy observations.
4. Don't add penalties for migration bytes, budgets, a context reset, resident-session caps or idle/offload without approval.
5. Do not describe S0's single-user radio scheduler as the final wired Max-Min network scheduler or GPU Processor Sharing; both are future modules.
6. Validate units, token/KV accounting, deterministic tie-breaking, end-to-end Turn completion, and event progress with tests.
7. Don't claim tests passed until actually run, and report the exact commands and results.
8. Keep credentials, SSH config, joblib artifacts, model weights, private data and large runs out of Git. No external code copy without source/license checks.
