# S1-B GPU slots and FCFS implementation plan

Goal: add a per-Edge admission controller over EqualShareGPU, using EventQueue.
Spec: user's pasted S1-B development task; integrated Section III with explicit
FCFS/no-priority override. Python 3.10.9, standard library, D-drive edits only.
No Git mutations, remote operations, KV admission, preemption or E2E extension.

Architecture: GPUQueue owns Ready records, a stable deque and admission timestamps.
EqualShareGPU alone owns admitted tasks' running status and remaining work.
All operations return one-shot GPUCompletion notifications, including zero work.
Ready events at priority 30 follow GPU completions at 20; external callers may
use phase 25 for cancellation. Due completions settle before each mutation; existing waiters precede arrivals.
Zero-work tasks wait normally, then complete synchronously when admitted.
Cancellation retains accounting and frees a running slot; completion wins exact ties.

Review focus: simultaneous releases/arrivals; zero-work queue draining; cancelled
waiters; stale predictions; invalid inputs that must not advance resource state.

- [x] Add tests/test_gpu_queue.py with independently calculated A-F expectations;
  run RED before implementation. E uses C=12 L=2: a(12) at 0, b(18) at .5,
  c(6) at .75; finish a=1.5, c=2.5, b=3; c starts=1.5, waits=.75.
- [x] Implement src/replacement/gpu_queue.py with ready/advance/cancel/handle_event,
  read-only combined task snapshots, derived running IDs/rates and waiting IDs.
- [x] Run suite GREEN; add gpu_queue_demo.py and s1b_gpu_queue_smoke.json,
  test real demo output and invalid configurations.
- [x] Update README, AGENTS and model adoption notes for S1-B complete / S1-C pending;
  document API, boundaries, hand calculations and upload manifest in docs/s1b_gpu_queue.md.
- [x] Review, run full suite, run S1-A/S1-B demos, preserve exact verification output.

User requests direct local implementation; no approval pause, branch or worktree.

Results: Python 3.10.9, 43 tests passed (7 S0 +17 S1-A +19 S1-B), raw output
in docs/s1b_test_output.txt; actual S1-B CLI output in docs/s1b_demo_output.json.
Both demos ran. Original engine and event queue were not modified.
RED runs observed for missing queue/demo modules and integer work/clock boundaries.

Independent review: no important FCFS/ownership/cancellation findings. A reported
extreme integer clock round-trip issue was reproduced; treated as an input
atomicity issue because partial admission must not survive a rejected call.
Fixed with pre-mutation validation and a RED-to-GREEN regression; suite 43/43.
Decision: reject integer clocks that lose precision through the existing decimal
float clock, rather than changing EventQueue's representation or S1-A. Such clocks
are unsupported; ordinary simulation inputs are unaffected. No deferred findings.
