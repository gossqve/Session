# S1-A GPU Dynamic Equal-Share

This report records the S1-A delivery. Foundation subsequently adapted S0 and
its config/safety tests; see `S1-Foundation_建模与实现对应报告.md` for current integration.
The resource module shares `replacement.events.EventQueue` with S0. No second
event engine was introduced. `gpu_demo.py` demonstrates concurrent generic Turn computation
from two Sessions; it is not a multi-session token/network/E2E simulator.

## Resource protocol

Instantiate `EqualShareGPU(queue, edge_id, capacity)` once per resource; use a
unique edge_id on a shared queue. Capacity is finite and positive in eq-work/s.
Generic tasks carry a unique string ID and finite nonnegative eq-work.
Prefill or Decode stages can submit generic tasks and use their returned IDs
to trigger the existing token/KV machinery later. Never submit future stages
to a policy observation. `tasks` contains simulator-only read-only snapshots
at the most recent settlement, not continuously updated wall-clock state.

- `submit(task_id, work, time_s)` settles old work, completes due tasks,
  admits new work, and recomputes shares and the next prediction.
- `advance(time_s)` settles an intermediate checkpoint. A caller must dispatch
  pending completion events before advancing beyond their scheduled time.
- `handle_event(event)` handles a current GPU prediction; foreign and obsolete
  events return an empty tuple without modifying time or resource state.
- `withdraw(task_id, time_s)` settles an explicit resource exit and retains
  remaining work in its history. This is an extension hook, not an implemented
  preemption policy. An exit exactly at completion yields normal completion.

**Consume the tuple of GPUCompletion returned by every method above**, including
submit and advance. This avoids losing zero-work or coincident completions.
Do not reenter resource methods from callbacks: the resource returns notifications
after the state transition, and the caller decides which events to schedule next.

At each membership change, old running work receives
`min(remaining, elapsed * capacity / old_running_count)` before rates change.
Idle periods consume zero work. Initial work always equals consumed plus remaining,
including withdrawn history. No token assumptions or real hardware timings enter
this resource.

One earliest-completion prediction is sufficient because all running tasks have
the same rate. A generation counter invalidates every old prediction when shares
change. Completion removes all tasks with zero remaining work, in explicit
admission order, before generating the next prediction. Same-time events use
the queue's (time, priority, insertion sequence) ordering. GPU completion event
priority 20 precedes demo arrival priority 30; these are event phases, not Session
or GPU task priorities. If an arrival is dispatched first at the completion time,
submit still settles and completes due tasks before admitting the arrival.

## Precision and scope

Internal decimal work, capacity and elapsed time are represented as standard-library
Fractions, so settlement cannot accumulate negative floating-point residual work.
Predictions round upward to the existing event queue's 1e-12 second grid; this can
delay a completion by at most one grid tick at ordinary simulation magnitudes.
At very large absolute times, float spacing is the effective resolution. Work
is capped at each task's remaining amount, so rounding never invents service.
This is a discrete-time numerical approximation of Processor Sharing, not an
RTX scheduler model. Fractions and retained history favor auditability in small
deterministic experiments; performance for large runs has not been benchmarked.
Stale queue entries are ignored when popped and may extend queue-drain time;
use actual completion timestamps for results, not the last stale event time.

S0's single-user wireless model is unchanged and is not wired Max-Min.
No authoritative files were present under docs/model_spec during the initial implementation.
The user subsequently supplied the integrated model; the current authority and
no-priority/no-preemption override are recorded in [model_spec/README.md](model_spec/README.md).
Foundation has removed S0's legacy service priority field. No service priority
or preemption behavior exists. S1-A itself adds no policy, admission or KV logic;
later stage integration is documented separately.

## S1-B extension

S1-B adds a separate controller owning L_e and stable FCFS; full KV recovery is
S1-C. Only admitted tasks call submit, so waiting tasks consume no
GPU share. On resource completion, consume notifications, release the running
slot/KV according to the model, then admit FCFS tasks at the same timestamp.
Keep admission policy and token/session lifecycle out of this resource.
Use `(arrival time, stable sequence)` as the FCFS tie-break, with no H/L classes.

## Hand calculations covered by tests

| Case | Observed contract |
|---|---|
| A | C=10, W=10: completion 1 s |
| B | Two W=10 at 0: rate 5 each, both finish 2 s |
| C | Second arrival 0.5: first consumed/remaining 5/5; finishes 1.5 and 2 s |
| D | Work 10/20/30 at 0: rates 10/3, then 5, then 10; finishes 3/5/6 s |
| E | Checkpoints 0.6/0.8/1/1.25: total service 10*t; individual conservation |
| F | Zero work, idle/restart, arrival/completion ties in both orders, invalid values, repeatability |

Additional tests cover explicit exits, obsolete/replayed completion events,
resource isolation, sub-tick work, nonterminating decimal deadlines, event
progress and the multi-session demo. All seven original S0 tests remain required.

## Actual local verification (2026-11-05)

Windows Python 3.10.9: `python -m unittest discover -s tests -v` passed
24 tests (7 S0 regression + 17 S1-A). Complete output is in
[s1a_test_output.txt](s1a_test_output.txt).
The GPU smoke CLI completed S1:T1 at 1.5 s and S2:T1 at 2 s, total work 20.
The unchanged S0 CLI also ran locally with mean E2E 0.7 s, observation end
1.4 s, final context 6 tokens, peak authoritative KV 24 bytes and released
authoritative KV 0 bytes. Its output was written to a new ignored runs directory
to preserve existing results. No server execution was performed.

Modified or added files (also the manual upload manifest):

```text
README.md
configs/s1a_gpu_smoke.json
src/replacement/gpu.py
src/replacement/gpu_demo.py
tests/test_gpu.py
docs/s1a_gpu.md
docs/s1a_test_output.txt
docs/superpowers/plans/2026-11-05-s1a-gpu.md
```

After uploading these files yourself, verify on the server:

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
```
