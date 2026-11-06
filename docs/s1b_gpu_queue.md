# S1-B GPU running slots and FCFS Ready queue

This is the S1-B delivery record. Foundation later adds typed Session/Turn/unit
bindings and adapts S0; current integration is documented in
`S1-Foundation_建模与实现对应报告.md`. Its GPUQueue engine remains unchanged.

## Implementation boundary

`GPUQueue` is a per-Edge admission controller wrapping the existing
`EqualShareGPU`; it uses the same global `EventQueue`. S0, S1-A, their configs
and all 24 existing tests are unchanged. Only admitted tasks enter the engine.
Waiting records do not receive a GPU rate, consume work or occupy slots.
The controller owns a deque and lifecycle timestamps; the engine remains the
sole owner of running status, remaining work, Fraction accounting, generations
and predicted completion events. Running IDs/counts are derived from its rates.

`capacity` is C in eq-work/s; `slots` is a separate positive integer L.
Neither parameter is inferred from the other. S1-B adds no KV limit, priority,
preemption, migration, networking, policy or complete multi-Session Turn E2E.

## API

```python
controller = GPUQueue(event_queue, edge_id="E1", capacity=12, slots=2)
completions = controller.ready("S1:T1", work=12, time_s=0)
completions = controller.advance(time_s=0.5)
completions = controller.handle_event(event_queue.pop())
completions = controller.cancel("S1:T1", time_s=0.75)
```

These lines illustrate alternative calls, not a single runnable scenario.
Consume every returned tuple of `GPUCompletion`, including Ready/checkpoint/
cancel calls; zero-work tasks can complete synchronously. Dispatch the global
queue chronologically and route GPU predictions to the owning controller.
Do not bypass the controller to mutate its private GPU. IDs are nonempty unique
strings for the controller's lifetime, including completed/cancelled IDs.

`tasks` is an immutable snapshot mapping, exposing `ready_time`, `start_time`,
`completion_time`, `queue_wait_s`, initial/consumed/remaining work, status and
`cancelled_time`. Waiting tasks have no start or completion timestamp and zero
consumed work. Their wait accrues up to the most recently settled resource time;
for started tasks it is exactly start minus Ready, with decimal subtraction.
Cancelled waiters accrue wait only until cancellation. Cancelled running tasks
retain consumed and remaining work but have no completion timestamp.

`rates`, `waiting_ids`, `slots`, `capacity` and `time_s` expose resource state.
`trace` records Ready/Start/Completion/cancel transitions; `gpu_trace` contains
the original engine's service and share-change records. These are internal
simulation diagnostics, not a policy observation or an E2E measurement.

## Deterministic scheduling and edge cases

Ready calls must arrive in nondecreasing simulation time; retroactive Ready
timestamps are rejected. With the chronological EventQueue this gives FCFS by
`(actual Ready time, explicit submission sequence)`. The deque's order is explicit;
metadata snapshots use a stored sequence. No Session/Turn ID lexical priority
or unordered set traversal determines admission.

Every Ready/checkpoint/cancel call settles engine service first. Due tasks
complete and free their slots before FCFS admission. Old waiters stay ahead of
new arrivals, even if a Ready call precedes the prediction event at the same
time. All simultaneous completions are processed before filling slots. Multiple
admissions occur at the same timestamp without elapsed service between them.
Intermediate share predictions are versioned and invalidated by the existing
engine; even an obsolete prediction with the SAME timestamp is ignored.

The demo uses GPU completion event phase 20 before Ready phase 30, then the
queue's insertion sequence breaks ties. These phases are not task priorities.
External callers can place cancellation events at phase 25 (after completion,
before Ready); the controller itself creates no cancellation events.

Chosen zero-work semantics: wait in FCFS if slots are full, then start and
complete at the same timestamp when admitted. A finite chain of zero-work
waiters drains without advancing the clock or bypassing earlier nonzero work.
This preserves the same admission rule for every task.

Cancellation removes a waiter or withdraws admitted work using S1-A's exit hook,
then fills released slots. It never reports cancelled work as completed.
Completion wins an exact-time cancellation tie. Repeated cancellation of known
terminal tasks is harmless; unknown IDs are errors. If a cancellation call is
processed before a prediction at the same time, due completions settle first,
then the target is cancelled before filling slots. If the prediction was already
processed, an admitted target may have start_time equal to cancellation_time;
it has received no positive-duration service at that timestamp. Thus cancellation
traces follow the explicit global event order; there is no hidden preemption rule.

## Hand calculations and tests

| Case | Hand-derived expected behavior, verified by tests |
|---|---|
| A: C=10, L=2, W=10/10 at 0 | Both start 0, rates 5 each, finish 2, wait 0 |
| B: C=10, L=2, W=10/10/10 at 0 | First two finish 2; third consumes no work while waiting, starts 2, finishes 3, wait 2 |
| C: C=10, L=1, arrivals 0/0.5 | Finish 1/2; second starts 1 and waits 0.5 |
| D: C=10, L=1, arrivals 0/0.5/0.75 | Finish 1/2/3; waits 0/0.5/1.25; extra tied waiter verifies stable submission order |
| E: C=12, L=2 | Detailed calculation below |
| F | Idle/restart, multiple slot releases, zero work, cancellation, invalid inputs, once-only completion, deterministic replay and Edge isolation |

E uses a: Ready=0/W=12, b: Ready=0.5/W=18, c: Ready=0.75/W=6.
From 0 to 0.5 a receives 6 work. From 0.5 to 1.5 a/b receive 6 work each.
a finishes 1.5, b has 12 remaining. c starts 1.5, having waited 0.75 seconds.
b/c each receive 6 work from 1.5 to 2.5; c finishes, b has 6 remaining.
b then receives 12 work/s and finishes 3. Total service is 12+18+6=36.

Additional tests reject invalid input without advancing valid task progress,
check preservation of integer input precision before Fraction conversion, and
exercise real demo output and invalid demo configurations.

## Local verification and demo

Python 3.10.9; run from the Windows repository root:

```powershell
python -m unittest discover -s tests -v
$env:PYTHONPATH = 'src'
python -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```

The 43-test suite includes all 7 S0 and 17 S1-A regressions and 19 S1-B tests.
Complete actual output: [s1b_test_output.txt](s1b_test_output.txt).
Actual CLI output including all share changes: [s1b_demo_output.json](s1b_demo_output.json).

| Task | Ready (s) | Start (s) | Wait (s) | Completion (s) |
|---|---:|---:|---:|---:|
| S1:T1 | 0 | 0 | 0 | 1.5 |
| S2:T1 | 0.5 | 0.5 | 0 | 3 |
| S3:T1 | 0.75 | 1.5 | 0.75 | 2.5 |

Shares on positive-duration intervals: [0,0.5): S1=12;
[0.5,1.5): S1/S2=6 each; [1.5,2.5): S2/S3=6 each;
[2.5,3): S2=12; after 3: idle. Total consumed work=36 eq-work.
No SSH, upload or Git mutation was performed. Earlier local modifications from
S1-A/model adoption were preserved, without attempting server synchronization.

## Limitations and S1-C interface advice

The existing engine's 1e-12-second upward event rounding and stale heap entries
remain. Use actual task completion timestamps, not the last popped stale event.
Integer timestamps that cannot round-trip through the engine's decimal float
clock are rejected before any controller mutation, rather than silently losing
time precision or leaving a partly admitted task.
Historical records and full traces are retained for auditing small deterministic
cases; large-run performance is not benchmarked. This stage has no pause/resume,
KVBlocked, token commit gate or full Turn delivery lifecycle.

S1-C should add a separate net KV resource with an atomic interface such as
`try_commit_tokens(session_id, token_count, bytes_per_token)` and
`release_session(session_id)`, plus read-only used/free byte accounting.
Compute completion must feed a token-commit gate; failure retains the completed
partial unit without counting a new Token/KV/output or recomputing the unit.
Add explicit `block`/`unblock` lifecycle support to the scheduler when requested,
preserving work and appropriate waiting accounting; current terminal cancellation
must not be repurposed as KVBlocked recovery. Check capacity before every legal
Token commit. GPU slot release and Session KV release are separate operations;
Decode completion alone must not free Session KV. These are proposed interfaces,
not implemented S1-C behavior.

## Local change / manual upload manifest

```text
AGENTS.md
README.md
configs/s1b_gpu_queue_smoke.json
src/replacement/gpu_queue.py
src/replacement/gpu_queue_demo.py
tests/test_gpu_queue.py
docs/model_spec/README.md
docs/s1b_gpu_queue.md
docs/s1b_test_output.txt
docs/s1b_demo_output.json
docs/superpowers/plans/2026-11-05-s1b-gpu-queue.md
```

This lists S1-B changes only. The server must also retain its existing S0/S1-A
files. The source model Markdown files are unchanged in this stage.
After manually uploading these files yourself, run:

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```
