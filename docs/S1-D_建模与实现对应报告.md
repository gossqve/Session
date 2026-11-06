# S1-D 建模与实现对应报告

2026-11-05；Windows Local；Python 3.10.9；仅标准库。
依据：用户本轮 S1-D 正式任务、开发建模注意.md 和完整整合 Section III。
未执行 SSH/SCP、Git Commit/Push/Pull/Reset、服务器或全局配置修改。

## 1. 审计结论与修正

原 ComputeRegistry 每个 Token 建一个独立 GPUQueue 任务；单元完成自动释放并补位。
在 L=1 时，等待 Session 会插入当前 Turn 的 Prefill/Decode 单元之间。
该模式可作为低层组件测试接口，但不符合本轮正式 Turn 级名额约束。

本轮扩展原 EqualShareGPU/GPUQueue 的 retained segment 协议，没有第二套运行集合：

1. 正式 Serving 首个单元用 `ready(..., retain_slot=True)`；同一 Turn 一段连续服务只占一个条目。
2. 单元完成产生原 GPUCompletion，原引擎条目转为 awaiting_unit，暂留名额。
3. 同一时刻 `continue_task` 加入当前已知下一单元的 work，保留原名额和队列起点。
4. `release_turn` 才释放并按原 FCFS 补位；该操作不是 cancel，也不再次产生同一单元完成通知。
5. awaiting_unit 是零时长事件边界，禁止带着未决边界向后推进正时间；预测暂停，全部同刻决定后重算。
6. 每个稳定事件检查点验证没有未决零速率边界、没有重复 Turn 条目、名额和算力不超限。

保留默认 atomic API，原 77 项测试与断言全部未删改。历史 S0 单 Session 及组件演示
继续兼容；正式多 Session 路径始终使用 continuous=True。
ComputeRegistry 拒绝把已有 retained Turn 又作为 atomic 任务提交，防止绕过名额约束。

## 2. 架构与状态所有权

simulation/serving.py 的 ServingSimulator 持有一份 EventQueue、一份 RuntimeState、
私有 WorkloadDriver，使用现有 ModelSpec/SessionState/TurnState/EdgeState、
GPUQueue/ComputeRegistry/KVResource/OnlineObservation。没有重复定义这些实体。
每个 Edge 的 GPU/KV 都使用同一全局队列。

| 所有者 | 权威状态/职责 |
|---|---|
| 原 EqualShareGPU | 实际运行资格、当前单元剩余 work、Fraction 服务、预测版本 |
| 原 GPUQueue | FCFS 等待、名额准入、连续服务段的 Ready/Start/Release 时间 |
| ComputeRegistry | 每单元身份与 Turn 服务段的映射；单元完成历史，不另存运行集合 |
| Session/Turn | 已提交 Context/Token、当前阶段、已交付输出、已发生的生命周期 |
| KVResource | 原子提交、PendingCommit、阻塞计时、真实释放与恢复通知 |
| ServingSimulator | 上传、当前生成边界、按事件消费通知、FIFO 下行、完整交付及下一轮 |
| WorkloadDriver | 未到达 Session、未来 Turn/Access、隐藏输出及离线分母 |

每单元 GPUComputeTask 保留 Session/Turn/phase/unit/Execution 身份。历史完成单元的
work 和完成时刻不受下一个单元影响；当前剩余 work 仍从原资源读取。
服务段 owner/unit 索引仅作身份映射，active 状态始终向 GPUQueue 查询。
Edge.running_tasks/ready_queue 也从同一资源条目派生。

## 3. 统一生命周期与事件顺序

私有驱动器安排 Session arrival；到达时才加入 Runtime/Observation 并读取当前无线参数。
首轮提交揭示当前输入，按 `8*input_tokens*text_bytes_per_token/uplink_bps` 上传。
输入实际到达后才设置 Ready。当前阶段要求固定 Access=Execution；跨 Edge 转发或
后续 Access 变化会明确报未实现，不能静默冒充 Network/Mobility。

连续 Prefill 只处理本轮新增输入；Decode 每次仅提交当前一个单元的模型 work。
下一输出是否存在只在合法生成边界询问私有 Driver，不把隐藏总输出变为 GPU 总量。
GPUComputeCompleted → 原 Runtime.commit_token → TokenCommitted；成功 Decode 才入下行队列。
每 Session 无线独立，同一 Turn FIFO 串行发送，单 Token 时长 `8*b_text/downlink_bps`。
下行可与后续 Decode 重叠。

生成结束立即释放 GPU 名额；等待最后一 Token 实际抵达才 TurnCompleted。
零输出须已有合法生成结束和完整输入处理。完成后同一时间戳提交下一轮，零 Idle。
最后一轮完整交付后自然结束并释放全部权威 KV。

每个事件先按 Edge ID 和稳定准入顺序结算所有资源，再按该顺序消费同刻完成通知，
然后执行到达/上传/下行/恢复事件。EventQueue 的 phase 仅是事件排序，不是服务优先级：
GPU=20，kv_retry=25，arrival/下一轮 submit=30，上传/下行=50，观测 checkpoint=90。
同刻更新中新创建的事件仍由原稳定 sequence 排序。所有零时长单元边界在本次事件内解决。
过期 GPU 预测先按原资源版本检查后丢弃，不推进观测时钟或制造未完成对象的额外等待。
advance_to 消费真正的 checkpoint，包含目标时刻之前的全部同刻 Ready/完成事件。

## 4. KVBlocked、恢复与异常

原 KVResource 继续检查 Context/净容量，失败没有部分提交。KVBlocked 保留已完成
GPUComputeTask、PendingCommit 和原 KV。执行器立即 release_turn，其他 FCFS Turn 可运行。
GPUQueue 等待只来自真实 Ready 区间，不把上传、KVBlocked 或仅下行计入其中。

真实 Session 结束触发 kv_retry 后，统一执行器消费 TokenCommitted，直接处理已提交
Token 的后续逻辑，不再 commit 或计算该单元。若需新计算，建立新 Ready 服务段并
重新加入原 FCFS；若已无计算，仅下行，不取得 GPU 名额。

ContextLimit 不能等待 KV 突破：释放运行资格，不提交非法单元。Prefill 尚不完整则
异常结束、不制造合法零回复；已有合法输出则先真实 Drain，再异常清理。该 Turn
不计正常完成。OutputLengthLimit 只结束本轮生成，合法后续 Turn 继续。
无合法释放机会时队列有限静止，保留 blocked/未完成和已提交 KV；无轮询、扩容或超时成功。

## 5. 指标口径和机器可读产物

Turn 明细包含 Session/Turn/Model/Access/Execution，提交、首个 Ready/Start、
累计 GPU Queue、实际 GPU work、输入/Prefill/Decode/交付计数、轮末 Context/KV、
KVBlocked 次数/时长、生成结束、完整接收/E2E、状态/原因。
轮末 KV 是清理前历史事实；Session/resource 最终 KV 是当前实际占用。
Queue 按服务段去重求和，单元 work 按实际服务逐单元累计，避免一段多单元双重计数。
未完成 Turn 的接收与 E2E 保持 null，不伪造时间；未提交轮次不创建虚构 Turn 行。

全量 planned_turns 仅在 results 离线评价中读取；完成率分母为全部计划 Turn。
只要有任一异常/未完成，全量 mean_full_turn_e2e_s 为 null。
completed_turn_p95_e2e_s 明确只用正常完成者，采用 nearest-rank（ceil(0.95*n)）。
同时输出实际 submitted/unfinished、GPU work/queue、KV block、同时总 KV 峰值和最终 KV。

CLI 为 replacement.demos.serving_demo。--out 必须是新目录，包含 summary.json、
turns.json/csv、sessions.json、resources.json、events.jsonl、gpu_events.json、
kv_events.json，以及仅供离线复现的 config.json；无 --out 则打印完整 JSON。

## 6. 强制手算 A 的实际逐事件核对

C=10、L=1，两 Session t=0 到达，输入/输出各 1，pre/dec work 各 1，
text=1 Byte/token，上下行独立 80 bit/s，S1 稳定在前，KV 充分。

| 时间 | 实际事件与状态 |
|---:|---|
| 0 | S1/S2 到达并提交首轮，各自开始上传 |
| 0.1 | 两者输入到达；S1 获得唯一名额，S2 FCFS 等待 |
| 0.2 | S1 Prefill 完成并提交；同名额连续 Decode，S2 不插队 |
| 0.3 | S1 Decode 完成、提交、开始下行；释放名额，S2 开始 Prefill |
| 0.4 | S2 Prefill 完成并连续 Decode；S1 最后输出抵达，Turn/Session 正常结束并释放 KV |
| 0.5 | S2 Decode 提交，释放 GPU，开始下行 |
| 0.6 | S2 输出抵达、Turn/Session 正常结束并释放 KV |

实际 E2E：S1=0.4、S2=0.6；S2 Queue=0.2；平均=0.5；GPU work=4；
peak KV=12、final=0。完整实际事件与资源记录见 s1d_hand_trace.json。
多 Token 证明：S1 输入3/输出3，S2/S3 在0.35/0.4就绪，S1 从0.3连续计算到0.9；
S2/S3 首次开始为0.9/1.0。S1 六个单元仍只对应一个 GPUQueue 条目。

## 7. 正式配置的实际结果

configs/s1d_normal.json 使用两个不同合成模型，分别为 4/8 Byte/token、
work 系数 1/1 与 2/2，两个 Session 各两轮。其余配置展示排队/恢复/安全静止。
没有虚构真实 Qwen/Phi/Llama 规格，没有手工指定计算、提交、释放绝对时刻。

| 配置 | 完成/计划 | 全量平均 E2E(s) | GPU Queue 总和 | KVBlocked 总时长 | GPU work | KV峰值/最终 |
|---|---:|---:|---:|---:|---:|---:|
| normal（L=2） | 4/4 | 0.6 | 0 | 0 | 12 | 32/0 |
| queue（L=1） | 4/4 | 0.6 | 0.4 | 0 | 12 | 32/0 |
| recover | 3/3 | 2.233333333333 | 0.1 | 2.5 | 8 | 20/0 |
| blocked | 0/4（仅2轮已提交） | null | 0.1 | 0.1（截至静止点） | 3 | 4/4 |

恢复配置自然产生：S2 先生成3个输出并慢速下行；S1 在0.6受阻，S2在3.1完成
最后交付并释放，S1原 Pending 单元在3.1提交，首轮3.2完整交付，第二轮立即提交并
在3.6完整交付。没有重算 Pending Token。永久阻塞配置在0.4有限静止，不伪造后续提交。
实际命令、输出目录、全部摘要见 s1d_scenarios.json；完整运行产物保留在唯一命名 runs 目录。

## 8. 建模 → 实体 → 接口 → 事件 → 测试 → 实际结果

| 建模定义 | 正式实体/接口 | 事件行为 | 新测试（tests/） | 实际结果 |
|---|---|---|---|---|
| 式(16) L 按 Turn 计 | 原 GPU._Task / GPUQueue retained API | 单元完成保留资格，合法边界继续/释放 | test_turn_gpu 全3项；Serving.test_a/test_b | 无Token间插队；每Turn最多一名额 |
| 式(17)-(18) 动态等份/守恒 | 原 Fraction GPU + typed units | 运行Turn增减重算，历史单元冻结 | test_c_two_turn_equal_share_then_full_capacity | 两Turn各5，剩余恢复10；GPU结束0.5/0.7 |
| 固定模型/多模型KV | ModelSpec/SessionState/KVResource | 每单元用权威模型系数 | test_e_distinct_models_work_and_kv | work=2/5，轮末KV=8/16 |
| 式(8) 多轮零Idle | Runtime/Driver/Serving._maybe_finish | 完整交付同刻下一轮 | test_d_multiturn_context_zero_idle_and_release | 4/4，均值0.45，Context各4 |
| 输入到达才Ready | Turn/Serving上传事件 | 真实输入字节/独立速率推进 | test_a；test_isolated_edges_and_late_arrivals | Ready=0.1；迟到Session未提前公开 |
| KVBlocked保留/恢复 | PendingCommit/TokenCommitted | 释放名额，恢复不重算 | test_f_natural_kv_block_recovery_no_recompute_e2e | E2E=1.2，阻塞0.6，4个唯一单元 |
| 恢复后新计算重入FCFS | GPUQueue服务段/Turn queue | 不把blocked算queue | test_recovery_next_unit_reenters_fcfs_excludes_blocked_time | Queue0.1、block1.6、E2E2.4 |
| 安全静止/异常 | Session/Turn状态/Runtime | 无轮询，无伪成功，Context不同于KV | test_g_permanent_block_and_context_failure_are_not_success | 均值null、Context不计KV block |
| 式(22) 流式完整交付 | FIFO队列/Turn.received_at | GPU结束后仍等最后输出 | test_h_streaming_fifo_overlap_waits_for_last_output | GPU0.5结束，3.3才收到完整响应，顺序1/2/3 |
| 同刻稳定/过期预测 | EventQueue phase/sequence/版本 | 同刻资源先结算，过期事件不推进时钟 | test_i；test_checkpoint_processes_all_same_time_ready_events | 结果完全一致，checkpoint含两个Ready |
| 异常Drain/输出上限 | completion_reason/Runtime | 已合法输出照常下行，输出cap不终止后续 | test_output_cap_zero_reply_and_context_drains_legal_output | cap后下一轮正常；Context异常先交付已有输出 |
| 式(33) 因果性 | 私有Driver/白名单Observation | 未来输出/Turn/Access/Session不泄露 | test_j_same_prefix_different_future_is_causal | 0.25时快照、事件、GPU/KV决定一致 |
| 回归兼容 | 原公开路径与atomic API | 不改变历史组件语义 | 全部原77项 | 全部保留并通过 |

最终全量 **94 项通过＝原77＋3 Turn GPU＋14 Serving**。完整逐项输出见 s1d_test_output.txt。
原 S0/S1-A/S1-B/S1-C 四入口也实际复跑，摘要见 s1d_verification.json。
独立代码审查未发现重要问题；自审另补同刻 checkpoint 和原子/连续模式混用拒绝测试。

## 9. 未来信息与接口边界

Runtime 只登记已到达 Session、实际揭示 Turn。到达计划、隐藏输出和后续 Access
留在私有 Driver；原 Config 不挂到 Runtime/Observation。在线只接收 observe 值，
不传 simulator、driver、resource、config 或诊断轨迹的引用。
新 Observation 只增加已发生的累计 Queue/work 和生成结束时刻，仍为冻结白名单 DTO。
当前单元 work 和已完成历史累积不是未来真实剩余输出 work。

连续 API 要求执行层在同一时刻消费所有完成通知并 continue/release；
它不提供 Turn 中途抢占或暂停策略。历史 atomic API 继续用于原组件用例。
所有新输出产物均为离线评价/审计，不是策略 Observation。

## 10. 文件、上传与运行

完整新增/修改相对路径及上传清单见 S1-D_file_manifest.txt；没有删除历史文件或结果。
主要新增：simulation/serving.py、demos/serving_demo.py、四份 s1d 配置、两个测试文件。
主要修改：原 GPU/GPUQueue/ComputeRegistry 连续服务接口、实体/观测/Driver、当前说明。
上传清单必须同时包含资源接口扩展和执行器，不能只上传新演示。
不要上传 runs、环境、缓存、凭据或权重；旧入口继续可用，无需服务器删除旧源码。

Windows 本地：

```powershell
Set-Location D:\software\yxyWork\gitcode\Session
python -m unittest discover -s tests -v
$env:PYTHONPATH = 'src'
$servingOut = 'runs/s1d_' + (Get-Date -Format 'yyyyMMdd_HHmmss_ffff')
python -m replacement.demos.serving_demo --config configs/s1d_normal.json --out $servingOut
```

另外三场景替换配置名为 s1d_queue.json / s1d_recover.json / s1d_blocked.json。
用户上传后，Ubuntu 建议（本轮未执行）：

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m replacement.demos.serving_demo --config configs/s1d_normal.json
PYTHONPATH=src python3 -m replacement.demos.serving_demo --config configs/s1d_recover.json
PYTHONPATH=src python3 -m replacement.demos.serving_demo --config configs/s1d_blocked.json
```

## 11. S1-E 待审计与当前限制

验收范围内未遗留已知正确性问题；尚未实现 S2 网络、S3移动、S4迁移、S5策略和 PPO。
多个 Edge 当前仅执行各自本地 Session，不创建有线流。无线独立配置，不作基站共享调度。
沿用事件网格/浮点时间和 Fraction 工作量；到达时间按原队列精度规范化，GPU完成预测向上取整。
S1-E 应复核全部字段/事件/指标映射、同刻事件协议、长序列数值误差、永久阻塞/异常
报告口径、不同Seed场景矩阵、服务器复测和最终版本清单。真实模型参数及大规模性能尚未校准。
本轮完成 S1-D，不据此代替 S1-E 总审计或后续网络/迁移模块验收。
