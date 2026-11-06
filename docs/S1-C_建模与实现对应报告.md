# S1-C 建模与实现对应报告

日期：2026-11-05。Windows Local，Python 3.10.9，标准库。
依据：用户本轮 C0/C1 正式任务、开发建模注意.md、完整整合 Section III。
只修改本地 D 盘项目；无 SSH/SCP、Git Commit/Push/Pull/Reset 或系统配置修改。

## 1. S1-C0：目录、移动与兼容

整理前：主要实现文件位于 src/replacement/ 根目录。
整理后只有 replacement 一个顶级包：

```text
replacement/
  core/          entities.py runtime.py workload.py observation.py
  resources/     gpu.py gpu_queue.py compute.py kv.py
  simulation/    events.py s0.py
  demos/         gpu_demo.py gpu_queue_demo.py kv_demo.py
  cli.py         保留原命令
  原公开模块      仅 import 或 main 转发
```

四个子包各有 __init__.py，均被实际使用。Model/Session/Turn/Edge 的定义在
core/entities.py；RuntimeState 从原 entities.py 拆出到 core/runtime.py。
资源与 core 的类型依赖用 TYPE_CHECKING，实体资源初始化采用局部导入；
不存在第二个 Entity、GPU、GPUQueue 或 EventQueue 实现。

实际移动实现（旧路径仍留轻量转发文件，不需在服务器删除）：

| 原路径（src/replacement/ 下） | 唯一实现的新路径 |
|---|---|
| entities.py | core/entities.py；RuntimeState 单独在 core/runtime.py |
| workload.py | core/workload.py |
| observation.py | core/observation.py |
| gpu.py | resources/gpu.py |
| gpu_queue.py | resources/gpu_queue.py |
| compute.py | resources/compute.py |
| events.py | simulation/events.py |
| s0.py | simulation/s0.py |
| gpu_demo.py | demos/gpu_demo.py |
| gpu_queue_demo.py | demos/gpu_queue_demo.py |

内部导入改用子包位置；cli.py 直接导入 simulation.s0。原 62 项测试的导入
路径由兼容入口继续支持，断言和安全覆盖未删除或改写。
新增 test_package_layout 检查新旧路径导出的每个主要类/函数是同一个对象。
原 replacement.cli、replacement.gpu_demo、replacement.gpu_queue_demo 均可运行。

**进入 KV 开发前已实际验收**：62 项历史测试 + 1 项导入兼容测试，63/63 通过。
原始输出见 s1c0_test_output.txt。三个旧入口均实跑，摘要见 s1c0_smokes.json：
S0=2/2、0.7 s、1.4 s、Context 6、KV peak 24、释放后 0；S1-A 完成 1.5/2 s，
work 20；S1-B work 36，最后完成 3 s。
机器可读移动清单见 s1c0_moves.json。

## 2. S1-C1：正式资源与唯一权威状态

resources/kv.py 的每 Edge KVResource 持有该 Edge 和唯一 Runtime 的引用，
只管理 PendingCommit 元数据、阻塞顺序、已提交单元审计、峰值和释放重试事件。
`used_bytes` 从 Edge.authoritative_kv_bytes 派生；该值始终是驻留 Session KV 求和。
不存在独立可漂移 used 计数器。模型沿用结构公式，不写死 4 Byte/token。

接口：

- `can_fit(additional_bytes)`：净 KV 容量门槛。未来承诺应扩展此门槛，当前不实现 Shadow/承诺。
- `try_commit(session_id)`：验证当前完整计算单元，原子检查并提交，返回 CommitResult。
- `pending`：按阻塞发生顺序和稳定 Session ID 的只读元组。
- `handle_event(event)`：真实释放触发的重试，返回 TokenCommitted 值通知。
- `release_session(session_id)`：只允许终态 Session 且无活跃 GPU 任务，幂等释放。
- `assert_consistent()`：验证驻留 Session 的 KV=结构字节*Context、执行归属和 Edge 净容量。
- `peak_bytes / trace`：历史审计；不参与在线策略或未来预测。

RuntimeState.commit_token 委托该资源。RuntimeState.end_session 检查合法生命周期，
设置自然或异常终态后释放，重复结束返回 0、不再次计释放或创建重试。
RuntimeState.handle_resource_event 负责 Edge 路由，通知由执行层消费。

TurnState.pending_commit 指向资源中同一个不可变 PendingCommit；没有复制一份
待提交 work。元数据含 Session/Turn/task/phase/unit、blocked_at、sequence。
实际已耗服务和剩余 work 仍由原 GPUComputeTask/GPUQueue 提供。
Turn 新增 block_count、blocked_time_s，blocked_since 从 pending 派生。
OnlineObservation 只加入已发生的阻塞时间/次数，不含资源、驱动器或事件引用。

## 3. 原子提交、阻塞与恢复

提交先校验驻留身份、Session 状态、当前已完成且未提交的任务、当前 Turn/阶段/
单元序号、实际 GPU 完成时间、输入处理及输出上限，再检查 Context 与净 KV。
所有检查通过后，一次事件内更新 Context、Session KV、有效 Prefill/Decode 计数、
已提交 work 及提交去重账目。GPU 未完成、重复提交或越过当前输入均不合法。

ContextLimit 在 KV 前检查，不进入等待显存的 pending 集合。失败 Token 不增长 KV。
原 S0 的已生成输出 Drain、异常清理、零输出合法结束和单轮 OutputLengthLimit
继续有效；单轮输出上限不结束仍有后续轮次的 Session。

KV 不足时，Session/Turn 保持 blocked（不失败、不成功），保留原 KV、当前完成
单元和 partial_work，记录真实开始时刻。重复尝试不重置起点或重复计阻塞次数。
有效输出计数不增，不创建该输出下行。GPUQueue 已处理该单元完成并释放名额，
其他 Ready 可以进入；没有调用终止性 cancel。

另一 Session 合法释放 KV 后，同一时间为本 Edge 安排一项 kv_retry 事件：
事件 phase=25，GPU 完成=20，通常 Ready/其他业务在其后。多个释放合并一项重试，
事件 generation 和 scheduled 标志防重复/过期执行。有效重试要求 Runtime 时钟一致。

局部恢复顺序为 `(block sequence, Session ID)`，逐项检查当前容量。
较早的大单元不足时仍保留，但允许稍后的小单元在自己的检查中利用空间；
这是确定性的局部资源重试规则，不是新的全系统布局策略或优先级。
每项成功提交产生一次 TokenCommitted，内含原 task/Session/Turn/阶段/单元和当前时刻。
不再次创建该 GPU 单元；后续新单元重新经过原 FCFS/Equal-Share。

无真实释放时不创建轮询事件，无恢复保证。事件队列静止后保留 blocked 和未完成，
不扩容、不设置超时成功、不伪造响应。S0 与演示都消费恢复通知；S0 仍只执行自己的
单 Session，统一多 Session 多轮执行层属于 S1-D。

## 4. 最小演示的真实事件摘要

入口：replacement.demos.kv_demo；配置 configs/s1c_kv_smoke.json。
正式 ModelSpec 派生 4 Byte/token，C=10、L=1、净 KV=12 Byte。
S1 本轮输入 2、输出 1；S2 输入 0、输出 1。每个已提交输出使用合成 0.5 s
交付延迟，因此 S2 在 GPU 完成后仍合法保留 KV，直到完整响应抵达用户。
私有 WorkloadDriver 决定生成边界，演示不暴露隐藏长度到在线快照。

| t(s) | 真实事件 | Session/阶段/单元 | Session KV | Edge used |
|---:|---|---|---:|---:|
| 0.1 | GPUComputeCompleted | S1 Prefill 1 | 0 | 0 |
| 0.1 | TokenCommitted | S1 Prefill 1 | 0→4 | 4 |
| 0.3 | GPUComputeCompleted | S2 Decode 1 | 0 | 4 |
| 0.3 | TokenCommitted | S2 Decode 1 | 0→4 | 8 |
| 0.4 | GPUComputeCompleted | S1 Prefill 2 | 4 | 8 |
| 0.4 | TokenCommitted | S1 Prefill 2 | 4→8 | 12 |
| 0.6 | GPUComputeCompleted | S1 Decode 1 | 8 | 12 |
| 0.6 | KVBlocked | S1 Decode 1，已耗 work=2 保留 | 8→8 | 12 |
| 0.8 | TokenDelivered | S2 Decode 1 | 4 | 12 |
| 0.8 | TurnCompleted | S2 | 4 | 12 |
| 0.8 | KV release | S2 自然结束 | 4→0 | 8 |
| 0.8 | Pending TokenCommitted | S1 Decode 1，无重算 | 8→12 | 12 |
| 1.3 | TokenDelivered | S1 Decode 1 | 12 | 12 |
| 1.3 | TurnCompleted | S1 | 12 | 12 |
| 1.3 | KV release | S1 自然结束 | 12→0 | 0 |

完整 JSON 事件（含 Model/Execution、GPU 名额状态、原因等）见 s1c_demo_output.json。
真实结果：4 个唯一计算单元、总 GPU work=6、恢复 1 单元、peak KV=12、final KV=0、
重复计算=false。恢复前后同一个 task_id，没有新增第五个计算任务。
演示是单轮脚本化资源验收，固定交付延迟不代表已实现共享网络或整个 S1-D Serving。

## 5. 建模规则 → 字段 → 函数 → 事件 → 测试

| 建模规则 | 实体字段 | 文件/函数 | 事件状态变化 | 对应测试 |
|---|---|---|---|---|
| 式(12) 结构 KV；多模型 | ModelSpec.kv_bytes_per_token / Session KV | core.entities / kv.try_commit | 实际提交各自增长 4/8 Byte | test_a_b_structural_kv_shared_capacity_and_other_edge；原 Foundation 结构测试 |
| 式(21) 净 KV 和驻留求和 | Edge._residents / Session KV | KVResource.used_bytes/assert_consistent | 同 Edge 相加、其他 Edge 独立 | test_a_b_structural_kv_shared_capacity_and_other_edge |
| 式(13) 原子提交 | Context/prefill_done/decode_done/committed_work | KVResource.try_commit | Completed→Committed；失败无部分写入 | test_c_boundary_atomic_block_and_duplicate_commit；原未完成计算/重复提交测试 |
| KVBlocked 保留 work 和 KV | Turn.pending_commit/partial_work/status/blocked_since | KVResource.try_commit | 未提交、blocked、名额释放 | test_c_boundary_atomic_block_and_duplicate_commit；test_f_gpu_slot_freed_and_resumed_next_unit_rejoins_fcfs |
| 真实释放可恢复 | PendingCommit / TokenCommitted | release_session/handle_event | release→kv_retry→提交→执行继续 | test_d_release_recovers_pending_unit_without_gpu_recompute；test_demo_uses_real_pending_units_and_no_recompute |
| 确定性部分恢复 | pending.sequence / 当前 free | KVResource.pending/handle_event | 逐个当前检查，不超额写入 | test_e_multiple_waiters_partial_deterministic_recovery |
| Context 不可等待突破 | completion_reason | try_commit / 原 S0 异常流程 | ContextLimit 无 pending 恢复 | test_g_context_limit_never_joins_kv_retry；原 Foundation Context 测试 |
| 单轮输出上限与零输出 | generation_complete/有效输出 | S0 与 kv_demo 的 continuation | 不错误结束后续 Turn；合法零回复 | 原 test_context_failure_not_success_and_output_limit_is_per_turn；test_recovered_prefill_can_finish_legal_zero_output_turn |
| 释放不重复、不提前 | status/end_time/residents | Runtime.end_session/KVResource.release_session | 终态后释放一次，保护其他 Session | test_h_release_idempotent_preserves_others_and_retry_is_once；test_direct_release_cannot_discard_active_session_kv |
| 无恢复保证、有限推进 | pending/status/received_at | 无轮询；原 EventQueue | 无资源事件则静止并保留未完成 | test_no_release_means_finite_quiescence_without_fake_recovery；test_demo_persistent_pressure_quiesces_without_completing_blocked_turn |
| 重试时钟/重复事件安全 | retry generation/scheduled | KVResource.handle_event | 错误时钟拒绝；重复事件无操作 | test_wrong_event_or_clock_does_not_consume_pending_retry；test_h_release_idempotent_preserves_others_and_retry_is_once |
| 因果、无未来信息 | Observation 标量/tuple白名单 | core.observation / KVResource | 不同未来计划当前决策相同 | test_i_unchanged_future_has_same_capacity_decision_and_observation；全部 Foundation 隐私测试 |
| 唯一实体、旧路径兼容 | 相同 class/function 对象 | 旧转发模块 | 导入及 CLI | test_legacy_and_canonical_imports_share_definitions |

## 6. 实际测试与审查结果

C0：63 项通过，包含全部原有 62 项；三旧 CLI 已实际运行。
C1：77 项通过，即全部历史 62 + 1 包兼容 + 14 KV 测试；历史测试未删改断言。
最终完整输出见 s1c_test_output.txt；四个演示摘要见 s1c_verification.json。
S0 基准仍为 2/2、mean E2E=0.7 s、end=1.4 s、Context=6、peak KV=24、释放后=0。
独立审查未发现重要问题。服务器未由本代理连接或运行；本轮只报告本地证据。

## 7. 完整文件与上传清单

完整相对路径见 S1-C_file_manifest.txt；逐项包含：四个新子包及其唯一实现、
旧路径的兼容转发、cli 导入修改、新 KV 演示配置、两份新测试、当前说明和审计产物。
移动清单另见 s1c0_moves.json。没有删除项目文件，也无需删除服务器旧文件；
上传时必须同时覆盖旧转发入口并复制新子包，不能只传 KV 文件。
不上传 runs、__pycache__、环境、凭据或权重。

Windows 本地：

```powershell
Set-Location D:\software\yxyWork\gitcode\Session
python -m unittest discover -s tests -v
$env:PYTHONPATH = 'src'
python -m replacement.demos.kv_demo --config configs/s1c_kv_smoke.json
python -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
python -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```

S0 CLI 兼容；--out 使用新的结果目录以保留历史数据。
由用户手工上传清单后，Ubuntu 建议执行（本轮未执行）：

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m replacement.demos.kv_demo --config configs/s1c_kv_smoke.json
PYTHONPATH=src python3 -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
PYTHONPATH=src python3 -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```

## 8. S1-D 衔接与保留边界

统一执行层在 GPUComputeCompleted 上调用 Runtime.commit_token，成功才生成输出
和调度下一单元；KVBlocked 时保持当前 pending。遇到 kv_retry 先结算当前资源，
消费 Runtime.handle_resource_event 返回的 TokenCommitted，只继续后续流程，
不得再次 commit 或重算该单元。所有后续新单元都走原 ComputeRegistry/FCFS。

S1-D 继续统一多 Session、多轮、输入上传、逐 Token 流式下行、队列/阻塞计时、
完整 Turn E2E、零 Idle 和完成率；需要明确整个运行 Turn 的名额生命周期，
沿用当前唯一实体而不把当前单元或 pending 当作另一个 Session。
本轮脚本化多 Session 资源验收不能替代 S1-D 的统一负载执行器。
Shadow/承诺、迁移、Max-Min、Mobility、Joint Re-placement、PPO 未实现。
保留现有事件时间精度及审计历史；没有大规模性能校准或真实模型参数定稿。
