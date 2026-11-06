# S1-Foundation 建模与实现对应报告

日期：2026-11-05。仅在 Windows Local 的 D 盘项目目录实施。
依据：`model_spec/开发建模注意.md`、用户 Foundation 任务及 2026-11-03 完整整合稿。
最新执行规范优先删除 Session 服务优先级，并禁止在线访问未来负载。
整合稿原文和两份核查附件保持原字节，保留版本追溯，不把其中旧 H/L 规则恢复到代码。
没有 SSH/SCP、Git 提交/同步、服务器修改或全局环境修改。

## 1. 本轮完成与阶段边界

建立正式实体、私有工作负载驱动、白名单在线快照和类型化 GPU 绑定。
S0 的单 Session 多 Turn 主路径已使用这些实体及原 S1-A/S1-B GPU 组件；
不是仅新增一套无人使用的 dataclass。原 GPU Equal-Share、FCFS 和 EventQueue
没有被重新实现。S0 普通场景的数值保持原值，但内部计算事件现在由原 GPU 引擎产生。

当前只完成 Foundation。多 Session 实体和共享 GPU 映射已有测试；
**没有实现多 Session 完整 Token/网络/E2E 执行闭环**，该部分属于 S1-D。
Token 原子提交门槛和最小 KVBlocked 状态不等于 S1-C 完整暂停/恢复执行器。

## 2. 原有字段迁移与唯一权威来源

| 原结构 | 正式字段/实体 | 来源与事件 |
|---|---|---|
| config.model / 固定 kv_bytes_per_token | 不可变 ModelSpec；结构派生 kv_bytes_per_token | 静态模型规格加载；不使用真实模型的虚构参数 |
| config.session 包含完整 turns 和 priority | SessionState 仅保存到达后的运行态；priority 删除 | session_arrival 创建；完整计划留在 Driver |
| S0 TurnState.output_tokens（隐藏总输出） | 私有 TurnPlan.hidden_output_tokens | Driver 只在当前生成边界给出是否继续的决定 |
| S0 input_tokens / prefill_done / decode_done / delivered | 正式 TurnState 同名当前计数 | 提交时揭示输入；合法 Token 提交和真实下行更新 |
| S0 的 Context/KV 独立计数器 | SessionState.context_tokens / authoritative_kv_bytes | RuntimeState.commit_token 原子更新 |
| Edge 重复计数风险 | authoritative_kv_bytes 为驻留 Session KV 求和 | 提交/释放立刻反映，无第二份可漂移计数器 |
| 字符串 GPU ID | GPUComputeTask 的明确身份/阶段映射 | ComputeRegistry 创建绑定；原 GPUQueue 保持计算与排队权威 |
| GPU 剩余 work、运行集合和队列 | 从 GPUQueue 派生的属性/视图 | 原引擎结算和事件版本机制；不复制进度或重新分配算力 |

## 3. 完整实体定义与职责

### ModelSpec（entities.py）

字段：`model_id, layers, kv_heads, head_dim, element_bytes,
context_window_tokens, output_limit_per_turn, prefill_work_per_token,
decode_work_per_token`。结构、窗口与输出上限为合法正整数；工作系数为有限正数；
ID 非空。frozen dataclass，Runtime 的模型注册表也是只读映射。

`kv_bytes_per_token = 2*layers*kv_heads*head_dim*element_bytes`，Byte/token。
合成 smoke 为 2*1*1*1*2=4；另一测试模型为 2*2*2*3*2=48。
没有新增 Qwen、Phi 或 Llama 的规格。

### SessionState（entities.py）

字段：`session_id, model_id, arrival_time, access_edge_id, execution_edge_id,
context_tokens, authoritative_kv_bytes, status, end_time, termination_reason,
turns`；`current_turn` 从已揭示的 turns 派生。turns 只含实际已提交轮次，
不是完整计划。Session ID、模型绑定和到达时间在创建后不可直接改写。
Access 和 Execution 分开存放；模型部署在接纳时验证。
无 priority 字段，slots 限定 schema，不允许任意追加旧字段。

### TurnState（entities.py）

字段：`session_id, index, input_tokens, submitted_at, prefill_done, decode_done,
delivered, gpu_ready_time, gpu_start_time, received_at, phase, status,
wait_reason, completion_reason, generation_complete, committed_work,
compute_task`。`remaining_gpu_work` 和 `partial_work` 从当前 GPU 单元派生。
没有计划输出总长、Session 剩余轮数、未来 Access 或预测完成时间。

Phase：upload/prefill/decode/delivery/end。状态区别 active、blocked、completed、failed。
首个 GPU Ready/Start 时间保存在 Turn 上，各单元时间仍以 GPUQueue 的记录为准。
GPU 完成不直接增加 Token 或 KV，更不直接完成 Turn；合法提交和完整交付是不同事件。

### EdgeState（entities.py）

字段：`edge_id, gpu_capacity, gpu_slots, kv_capacity_bytes, deployed_models,
event_queue, compute, _residents`。前三种资源分别使用 eq-work/s、Turn 名额、Byte。
GPU 参数/部署固定；compute 是现有 GPUQueue 的类型化适配器。
`running_tasks`、`ready_queue` 从原队列派生；驻留 KV 从实际 Session 求和。
没有 Session 人数上限、Shadow、迁移状态或第二个资源计数器。

### GPUComputeTask / ComputeRegistry（compute.py）

映射字段：`task_id, session_id, turn_index, phase, unit_index,
execution_edge_id`。`remaining_work, consumed_work, status, ready_time,
start_time, completion_time` 从原 GPUQueue 派生，适配器不重复算 work。
任务 ID 是内部键，不再作为完整 Session 的替代物。

ComputeRegistry 校验真实驻留 Session 身份、当前 Turn、输入已到达、
合法阶段/单元序号、Execution、部署兼容和 Runtime 的唯一 ModelSpec 实例。
Ready 时间必须等于当前 Runtime 时钟且不早于 Turn 提交，非法调用在队列变更前拒绝。
绑定不含剩余未来输出，当前任务只代表一个当前 Prefill/Decode Token 单元。

## 4. WorkloadPlan 与在线信息隔离

`workload.py` 中的冻结 WorkloadPlan/SessionPlan/TurnPlan 包含完整生成计划。
WorkloadDriver.from_s0_config 把原配置中的值复制成不可变计划。
完整样本的格式检查属于私有离线输入验证，不做未来 Context/KV 需求预测。

揭示边界：到达时创建 SessionState；实际提交时 reveal_turn 只返回当前输入和
当前 Access；每个 Decode 生成边界只询问 has_output 的继续/终止结果。
后续轮数只在当前 Turn 完整交付后由驱动器判断；全量分母仅最终离线评价读取。
未来 Access 变化在 S0 真正揭示时会明确拒绝未实现的 Mobility，而不会提前影响初态。

`observation.py` 采用显式 DTO：OnlineObservation、SessionObservation、
TurnObservation、EdgeObservation、TaskObservation。全部 frozen+slots，嵌套容器
使用 tuple，字段只包含拷贝后的标量/其他白名单 DTO，无回调或源对象引用。
没有 Simulator、Runtime、Driver、Plan、原 Config、事件队列、GPU 调试轨迹引用。
计算 work 仅是已揭示当前单元的进度，不是实际剩余整个输出。

策略仅应接收 `observe(runtime)` 或 `simulator.observation()` 返回值。
禁止给策略传 simulator/runtime/driver/config；本阶段没有策略对象或 PPO 接入。
这是明确的数据能力边界，不声称在同一 Python 进程中提供恶意反射代码沙箱。
CLI 保存完整 config.json 是离线复现实验产物，不是在线 Observation。

隐私测试构造相同当前输入、不同本轮隐藏输出总长、后续 Turn/输入/Access 的两份计划：
前四个实际事件和 Observation 相同，GPU 决策相同；序列化递归字段审计确认没有
计划字段或可遍历源引用；修改原 Config 和后续 Runtime 不会修改已生成快照。
每个实际全局事件还结算当前 GPU 进度，下行与 Decode 重叠时 Observation 不显示旧 work。

## 5. S0 未来预检查整改及历史测试修订

删除构造器对未来全部输入/输出的求和及全 Session Context/KV 预判。
当前输入在提交后才揭示；实际 GPU 单元完成后，RuntimeState.commit_token
按当前已提交 Context 和当前驻留 KV 检查，成功后同时更新 Token、Context、KV。
重复提交、未完成计算的提交、超出当前已揭示输入的 Prefill、非法 Decode 均拒绝。

KV 不足：不提交 Token/KV/下行，保留已完成单元的 partial_work 和已有合法 KV；
状态为 blocked，GPU 计算名额已释放。继续处理已存在的下行，但不能完成阻塞 Turn。
没有恢复扫描、自动重试、暂停/恢复队列或取消冒充恢复。

Context 不足：不提交超限 Token，标记 ContextLimit。若正在 Prefill 且输入未处理完整，
不制造零输出成功，直接异常结束；已有合法输出时先真实交付完，再异常结束及释放 KV。
该 Turn 不计入 completed_turns，全量平均为 null，未完成计划数保留。
输出长度上限是单 Turn 约束，达到后可合法结束本轮，后续轮次仍按驱动器继续。

保留并修订的两个原测试（没有删除用例）：

| 测试 | 旧假设 | 新断言与安全覆盖 |
|---|---|---|
| test_unsafe_capacity_rejected_without_fake_success | 构造时按未来总需求拒绝 20 Byte 容量 | 运行时第一轮完成；第二轮停在 Context=5/KV=20，待提交 Decode 不增加计数，partial_work=2，GPU 空闲，KVBlocked，均值不可计算 |
| test_context_window_is_across_all_turns | 构造时按全部未来 Token 拒绝 Window=5 | 第一轮成功；第二轮实际累计到 5 后 ContextLimit，无超限写入、不记成功、异常清理后 KV=0、均值不可计算 |

其他原 S0 5 项和 S1-A 17 项、S1-B 19 项测试保持语义；GPU 测试文件未修改。
正常 smoke 的 2/2、0.7 s、1.4 s、Context=6、KV peak=24、释放后 0 均实跑验证。

## 6. 建模 → 字段 → 接口 → 事件 → 测试

测试短名均位于 tests/test_foundation.py，标注 S0 者位于 tests/test_s0.py。

| 建模定义 | 实体字段 | 代码文件/函数 | 运行事件 | 测试用例 |
|---|---|---|---|---|
| 式(12) 结构 KV | ModelSpec 结构字段/kv_bytes_per_token | entities.ModelSpec | 模型加载 | test_b_structural_kv_formula_and_validation |
| 式(6) 固定模型（删除 priority） | SessionState.model_id | entities.SessionState.__setattr__/RuntimeState.add_session | session_arrival | test_a_sessions_bind_distinct_models_and_independent_state |
| 模型部署、Access/Execution 独立 | deployed_models / access_edge_id / execution_edge_id | RuntimeState.add_session | 接纳 | test_a_edge_resources_and_deployment_are_independent |
| 单 Session 单当前 Turn | SessionState.current_turn/turns | RuntimeState.submit_turn | submit_turn | test_session_arrival_and_single_current_turn_guards |
| 式(8) 零 Idle、式(9)/(13) 累计提交 | Context/KV/turn counters | RuntimeState.commit_token / S0._finish_turn | GPU 完成→提交；下行→下一轮 | test_c_compute_completion_is_not_token_commit_or_full_delivery；S0.test_two_turn_hand_calculation_and_zero_idle |
| 式(15)/(18) 已提交/部分服务守恒 | committed_work / partial_work / remaining_gpu_work | compute.GPUComputeTask / 原 GPUQueue | 当前单元服务与提交 | test_runtime_token_guard_is_atomic_and_retains_blocked_work |
| 式(16)/(17) 名额与等权 | EdgeState.running_tasks/ready_queue | ComputeRegistry / 原 GPUQueue/EqualShareGPU | Ready、完成、补位 | test_c_typed_tasks_reuse_fcfs_and_have_unique_ownership；全部 S1-A/B 测试 |
| 输入到达后才 GPU 就绪 | TurnState.phase/wait_reason | RuntimeState.input_arrived / ComputeRegistry.submit | upload_done→Ready | test_compute_requires_arrived_input_and_cannot_repeat_committed_unit |
| 唯一模型参数与合法时钟 | Runtime.models / GPUComputeTask 身份 | ComputeRegistry.submit | Ready 前校验 | test_compute_cannot_override_canonical_model_with_same_id；test_compute_ready_clock_must_match_runtime_after_turn_submission |
| 真实事件原子容量 | Session KV / Edge KV / CommitResult | RuntimeState.commit_token | Token 提交门槛 | 两项修改的 S0 安全测试；test_runtime_token_guard_is_atomic_and_retains_blocked_work |
| 式(22) 完整响应才完成 | decode_done/delivered/received_at | RuntimeState.finish_turn / S0._downlink_done | 下行完成 | test_c_compute_completion_is_not_token_commit_or_full_delivery；S0.test_completion_waits_for_output_delivery |
| 异常不得冒充成功 | completion_reason/status | S0._gpu_done/_finish_turn/_end_session | ContextLimit；已生成输出 Drain | test_context_exhaustion_during_prefill_never_creates_legal_zero_reply；test_context_exhaustion_drains_already_generated_response_before_cleanup |
| 会话自然结束释放 KV | Session KV / Edge resident sessions | RuntimeState.end_session | session_end/kv_release | test_arrival_visibility_and_release_share_one_authoritative_state |
| 无未来泄露 | WorkloadPlan 与 Observation 白名单分层 | workload.WorkloadDriver / observation.observe | 提交与生成边界；快照 | test_d_same_history_different_future_has_identical_observation_and_decisions；test_d_observation_is_detached_readonly_whitelist |
| 当前服务进度 | TaskObservation.remaining_work/consumed_work | S0.step/ComputeRegistry.advance | 下行与计算交错 | test_observation_settles_current_unit_at_interleaved_delivery_event |
| 删除 H/L，保留事件 phase | Session schema无 priority / Event.priority仅事件排序 | workload 输入迁移检查 / events.EventQueue | 配置加载；同刻事件 | test_e_no_service_priority_in_entities_or_current_config；test_legacy_service_priority_is_rejected_as_removed_schema；原 FCFS 测试 |

## 7. 实际验证与审查

Windows Python 3.10.9。全量 62 项测试：S0 7（2 项按新语义修订）+ S1-A 17
+ S1-B 19 + Foundation 19。实际逐项输出见 foundation_test_output.txt。
三个 CLI smoke 的实际输出摘要和一个白名单 Observation 实例见 foundation_verification.json。
未声称 S1-B 或 Foundation 已在服务器通过。

独立审查发现的两项接口问题均已复现并用 RED→GREEN 测试修复：
同 ID 的另一 ModelSpec 不再能替代权威规格；GPU Ready 不再能使用早于当前 Turn
或不同于 Runtime 当前时钟的时间。模型注册表只读。未遗留该两项问题。

## 8. 后续接口与未实现功能

- S1-C：围绕 RuntimeState.commit_token 的 CommitResult 建立完整容量管理、
  pending 单元提交/重试、阻塞释放与恢复；保留 GPUComputeTask 的已耗服务，
  不能 cancel 后重做或重复提交。当前终态取消接口不能作 KVBlocked 恢复。
- S1-D：以 RuntimeState/EdgeState/ComputeRegistry 为同一实体源，调度多个 Session
  的上传、单元服务、合法提交、流式交付和下一 Turn。集中消费所有类型化完成通知，
  每个事件结算各资源；运行中 Turn 的名额不能错误地按多个当前单元重复占用。
- S2–S7：有线 Max-Min、Mobility、Migration、Check、策略和 PPO 未实现。
- 结构式限于当前全上下文、同构 Attention 的合成规格；真实模型结构和参数仍待定。
- 沿用现有事件时间精度和 Fraction 服务机制。历史实体/任务留存便于审计，未做大规模性能校准。

Foundation 的数据/接口基础已可用于下一阶段，但不能据此验收整个 S1 Stateful Serving。

## 9. 本轮新增、修改、删除与上传清单

新增：

```text
src/replacement/entities.py
src/replacement/compute.py
src/replacement/workload.py
src/replacement/observation.py
tests/test_foundation.py
docs/model_spec/开发建模注意.md
docs/S1-Foundation_建模与实现对应报告.md
docs/foundation_test_output.txt
docs/foundation_verification.json
docs/superpowers/plans/2026-11-05-s1-foundation.md
```

修改：

```text
src/replacement/s0.py
src/replacement/events.py
src/replacement/cli.py
configs/s0_smoke.json
tests/test_s0.py
README.md
AGENTS.md
docs/model_spec/README.md
docs/s1a_gpu.md
docs/s1b_gpu_queue.md
```

删除文件：无。删除的是旧业务 priority 字段/校验、固定 KV 配置项和未来总负载容量预检查。
以上 20 个文件为本轮手工上传清单；服务器需保留原 S1-A/B 源码和测试。
无须上传 runs、缓存、旧 Config 或私有凭据；S0 config.json 输出仅作离线复现资料。
开发规范原始字节 SHA-256：3b68ff3990ba2099ecfa54715c768d0132eb4b351862716d78804c52d3518948。

Windows 本地：

```powershell
Set-Location D:\software\yxyWork\gitcode\Session
python -m unittest discover -s tests -v
$env:PYTHONPATH = 'src'
python -m replacement.cli --config configs/s0_smoke.json --out runs/foundation_manual_smoke
python -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
python -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```

CLI 的 --out 请使用新的结果目录，保留历史结果。实际本地验证使用唯一命名目录。
由用户上传上述文件后，在 Ubuntu 建议执行（本轮未执行）：

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m replacement.cli --config configs/s0_smoke.json --out runs/foundation_manual_smoke
PYTHONPATH=src python3 -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
PYTHONPATH=src python3 -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
```
