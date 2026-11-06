# S1-E 最终建模一致性审计报告

日期：2026-11-06。项目：`D:\software\yxyWork\gitcode\Session`。
本轮只修改 Windows 本地项目。Python 3.10.9，全部使用标准库。

**结论：S1 达到本轮本地最终验收条件。原 94 项测试文件逐字节保留，新增 16 项，合计 110 项全部通过；八个实际 CLI 演示回归与历史基准一致。未发现阻止进入 S2 的 S1 正确性问题。**
本轮没有连接服务器，没有执行 SSH、SCP、Git Commit/Push/Pull/Reset 或全局环境修改。
用户已完成的 Windows/Ubuntu S1-D 验证属于此前验收；本报告不把它写成本次 Ubuntu S1-E 已通过。

## 1. 依据、版本与执行边界

已审查 AGENTS.md、开发建模注意.md、Foundation/C/D 报告、原整合稿、2026-11-06
最终核查修订稿及网络可达性补充、全部当前源码/配置/测试。源码/测试/配置共 48 个
Python/JSON 文件，均完成语法/格式检查，全部 30 个 replacement 子模块实际导入成功。
独立只读审查补充复核了资源所有权、连续计算、KV 恢复、Token 归属和兼容入口。

用户最新 S1-E 请求是开发指令；建模附件是模型依据，里面的历史优先级、抢占、
R2A 内部选择器以及早期上传建议不构成本轮恢复机制或远程操作的授权。
固定模型继续由 Session 入场配置绑定，不实现内部模型选择。

两份桌面 2026-11-06 ZIP 原文保留在 `model_spec/2026-11-06-final/` 和
`model_spec/2026-11-06-reachability/`，没有覆盖 2026-11-03 历史整合稿。
采用后者的完整主文；它与前者相比仅进一步明确未来移动后 Access/原 Execution
组合的双向正常 Serving 路径预检，未改变 S1 数值。来源与逐文件 SHA-256 见
[s1e_model_sources.json](s1e_model_sources.json)。

新增规定：独立秒级移动机会、合法邻接 Markov、计划与实际 Access 分离、Turn 内
Handover、生成 Token 来源/路径保留、零 Idle。**本轮只补实体与语义；这些移动和
网络运行功能仍属于 S2/S3/S4。** 没有恢复 H/L、抢占、迁移惩罚/预算、Idle/Offload
或 Session 数量硬上限。

## 2. 修改前实体审计与最小决定

| 对象 | 修改前已有且正确 | 实际缺口 | 本轮处理 |
|---|---|---|---|
| ModelSpec | 固定 ID、结构 KV、累计 Context Window、逐轮输出上限、Prefill/Decode 系数 | 无 | 原定义/公式不变；不虚构真实模型参数 |
| EdgeState | 独立 C/L/KV、部署、唯一 compute/kv、驻留引用 | 没有 Area | 新增可空静态 area_id；None 明确历史未指定 |
| SessionState | ID/到达/固定模型、当前 Access/Execution、累计 Context/KV、生命周期、实际 Turn | 初始 Access 只在私有计划及部分日志中，Runtime 无稳定入网快照 | 新增不可变 initial_access_edge_id，不复制当前 Access 权威值 |
| TurnState | 实际输入、有效 Prefill/Decode/交付计数、时间/资源等待/状态 | 原结果把 Session 当前 Access 当整轮 Access；无正式输出对象 | 保存 submitted_access_edge_id；持唯一已生成 OutputToken 序列 |
| 输出 FIFO/事件 | 正确生成后发送、FIFO、重叠、完整 E2E | 队列只存输出序号，来源和文本字节未固化 | 使用同一个冻结 OutputToken；事件使用其全局 ID |
| Workload | 完整私有计划、按事件揭示、隐藏输出长度 | TurnPlan 含必填逐轮 Access | 正式 TurnPlan 仅输入/隐藏输出；旧字段隔离到私有兼容映射 |
| GPU/KV 资源 | Turn 名额、原子提交/恢复/释放 | 本轮无需另建资源 | 复用全部现有资源；GPU/Queue/Compute 算法没有改动 |

未建立 Area、DirectedLink、NetworkFlow、MobilityPlan 空壳、移动事件、影子 KV 或迁移
状态机。没有重复创建模型属性、当前 Access、独立 Edge KV 用量或第二个 GPU Run 集合。

## 3. 字段唯一权威来源与生命周期

| 字段/数据 | 唯一拥有者、创建与变化 | 派生/使用者 |
|---|---|---|
| ModelSpec 全部结构/限制/系数 | Runtime 模型注册表中的冻结对象 | compute/KV 必须使用同一模型对象 |
| Edge.area_id | Edge 创建时从配置读取；不可改；默认 None | Observation 复制静态值；S2 将严格验证 Area 注册关系 |
| Session.initial_access_edge_id | Session 初始化从初始 access_edge_id 快照；不可改 | 历史入网审计，不用于当前路由 |
| Session.access_edge_id | Session 当前实际 Access 的唯一字段，仍可变 | 当前观察和成功生成时的快照；没有新增实际切换执行器 |
| Session.execution_edge_id | Session 当前唯一权威 Execution | 原驻留表/compute/KV；不得因 Access 变化自动改变 |
| Session.text_bytes_per_token | 入场时由私有 SessionPlan 的已知网络配置赋值，正整数且不可改；组件默认 1 | 上传字节与输出记录；不是 ModelSpec.kv_bytes_per_token |
| Turn.submitted_access_edge_id | Runtime.submit_turn 在实际提交时保存 | Turn 结果快照；旧 access_edge_id 列为它的兼容别名 |
| Turn._output_tokens | KVResource.try_commit 成功 Decode 后追加，公开 output_tokens 返回 tuple | FIFO 引用同一对象；结果导出实际记录 |
| OutputToken 的身份/时间/来源/字节 | 冻结 dataclass；合法提交时创建，此后不随位置变化更新 | FIFO、下行耗时、事件关联、离线结果 |
| Turn.decode_done | 原 KV 提交一次增加 1 | 必须等于 output_tokens 长度；两者在同一原子转换更新 |
| Turn.delivered | 原 Runtime.deliver_token 推进唯一 FIFO 已交付前缀 | Token 的交付状态由 output_index <= delivered 派生，没有每 Token 可变 flag |
| Token.received_at 结果列 | 从实际 downlink_done 事件按 token_id 离线关联 | 仅输出结果，没有第二个运行期交付 ledger |
| Session.authoritative_kv_bytes | 原成功 KV 提交增长；Session 终态释放为 0 | Edge 用量按驻留 Session 求和；不含文本缓冲 |
| GPU Run/Ready/部分 work | 原 EqualShareGPU + GPUQueue，ComputeRegistry 仅映射身份和历史单元 | Edge/Observation 派生；无并行调度器 |

初始 Access 不能从“当前值”长期可靠恢复，因此新增入网快照有实际用途。
Turn 提交快照只是过去事实，不能作为未来整个 Turn 的固定 Access；当前值仍只存在
Session。未来 S3 必须经保护、邻接和可达性校验后的受控接口修改当前值；直接赋值
不是 Handover 功能。本轮测试中的显式字段更新只用于低层快照隔离检验，不是移动演示。

## 4. 输出 Token 接入证明

`core/entities.py::OutputToken` 保存：session_id、turn_index、output_index、
generated_at、execution_edge_id、access_edge_id、text_bytes。
`token_id` 为上述前三项的 tuple，序号在每 Turn 从 1 开始。

实际路径如下：

1. 原 GPUComputeTask 当前单元完整计算后，Serving 调用 Runtime.commit_token。
2. 原 KVResource.try_commit 检查任务身份、计算完成、当前序号、逐轮输出上限、
   累计 Context 和当前净 KV。任何失败均不能产生有效输出记录。
3. 只有所有检查通过的 Decode，才构造冻结 OutputToken。时间取**实际合法提交时刻**；
   来源取该时刻 Session 的权威 Execution 和实际 Access。然后在同一状态转换更新
   Context/KV、decode_done 和唯一输出序列。
4. Serving._committed 取得该同一对象，追加原 Session 下行 deque；_start_downlink
   直接使用 token.text_bytes 计算 `8*Byte/bit_per_second`，事件携带 token_id。
5. Runtime.deliver_token 在推进前缀前校验身份；重复、跨 Turn、跨 Session 或跳序
   ID 均拒绝。Serving 同时校验实际 Turn 和下一个序号，FIFO 完整到达才推进一次。
6. 原 S0 FIFO 也改为引用 OutputToken，并沿用同一个 Runtime/KV；原组件默认
   deliver_token(session_id) 仍交付当前下一个合法 Token，保持旧调用兼容。

Token 对象不含未来 Token、隐藏输出总数、预测结束时刻、计划 Access 或后续路径。
没有复制第二份 Token ledger，没有新增流、旧 Access 转发、Draining 或迁移路径。
未来网络阶段须在该不可变生成来源之上建立各阶段进度，不能反向修改来源。

可复算证据（新增测试）：

- 输入 1、输出 3、GPU C=10、每 Token work=1：有效生成时刻 0.3/0.4/0.5 s，
  ID 分别 (S1,1,1)/(S1,1,2)/(S1,1,3)，来源均 E/E。
- 下行 8 bit/s、每 Token 1 Byte：完整到达 1.3/2.3/3.3 s，FIFO 恰好一次；
  生成结束 0.5 s，完整 Turn E2E 为 3.3 s。
- Recover 配置：S1 Decode 1 在 0.6 s 计算完成并 KVBlocked；0.7 s 检查时无输出记录。
  3.1 s 原 Pending 合法提交才生成 (S1,1,1)，generated_at=3.1，不冒用 0.6。
- 文本 3 Byte/token、结构 KV=4 Byte/token、输入 1/输出 2：输出文本各 3 Byte，
  总累计 Context=3、KV峰值=12 Byte，E2E=1.1 s。文本不占 KV 容量。
- Context Window=2、输入1/计划输出3：只保留已合法提交的一个输出，不产生第二个
  失败输出；异常响应排空后结束，不能算正常完成。

## 5. Workload 与未来移动解耦、兼容性

正式 `SessionPlan` 保存固定模型、到达、初始 Access/Execution、私有 Turn 工作负载及
已知无线配置；`TurnPlan(input_tokens, hidden_output_tokens)` 不再含 Access。
`RevealedRequest` 只揭示当前输入。

旧 JSON per-Turn Access 不进入 TurnPlan，加载器单独保存私有兼容映射：未提供即使用
Session 初始接入；提供相同值作为固定接入断言接受；不同值在对应 Turn 揭示时明确
NotImplementedError，且尚未提交这个 Turn。不能静默移动，也不因未来差异提前改变
在线资源行为。格式合法性可离线验证，但没有未来容量/Context 适配预测。

**有意的程序化 schema 变化**：`TurnPlan(输入, 输出, Access)` 的第三参数已移除，
改用两参数；`RevealedRequest.access_edge_id` 已移除。唯一仓库内程序化旧调用
kv_demo 已适配。不能声称所有旧构造 API 完全无变化。旧模块导入路径、GPU 原子
任务 API、Runtime 的旧提交/交付调用和全部 CLI 保持可用；原 94 测试不需修改。

没有实现 Markov 采样或独立移动计划类。S3 的接口约束已记录：按到达时间 + 检查序号
推进独立私有过程，随机数由共同 Seed/稳定 Session ID/检查序号确定，保持计划链顺序，
不能依赖 GPU 速度、实际输出或运行期随机调用顺序；只安排下一次必要检查，Session
终止取消无用检查。未来位置、RNG 状态、私有 Driver 均不得进入 Observation。

S1 自动执行始终固定 Access=Execution；不是把 Access 设计成只能在 Turn 边界更新，
而是当前没有启用任何移动执行器。Area None 的旧测试可继续运行，S2 正式拓扑必须
显式填 Area 并验证存在性/归属，不能把 None 视为某个真实区域。

## 6. 全 S1 资源、生命周期与指标审计

### A. Session / Turn

Session 模型/ID/到达不可改；Runtime.submit_turn 只允许 active 且无未完成 Turn。
新增输入上传后只计算本轮新 Prefill，Context 跨轮累计。Serving._maybe_finish 仅在
合法生成结束且 delivered==decode_done 时调用 finish_turn；下一轮在相同时间安排
一次提交，没有用户 Think Time/Idle。最终自然结束释放全部权威 KV。
输出上限独立于 Session 总 Context；异常不能冒充合法零回复。

### B. GPU Turn 名额与守恒

正式 Serving 仍唯一使用原 ComputeRegistry.submit(..., continuous=True)。同一 Turn
连续 Prefill/Decode 共享一个 retained Queue entry；Token 单元完成进入 awaiting_unit，
执行层须在同刻 continue 或 release 后才允许正时间推进。原 GPU 时间门槛阻止跳过
这个边界，资源稳定快照拒绝残留零速率占位。不会每 Token 重新排 FCFS。

运行集合唯一由 GPU 维护，`|R_e|<=L_e`；非空时每个计算 Turn 获得 C_e/|R_e|。
FCFS 按 Ready 时刻与稳定提交序号；等待、上传、下行、KVBlocked 均不消耗 GPU。
部分工作量用 Fraction 累计；完成预测向上取 1e-12 s 网格，过期版本在推进时钟前丢弃。
同刻多资源先结算、再逐个处理实际完成，所有 retained 边界同刻解决；不存在中间
零时长微步骤的虚假服务。KVBlocked 释放名额；恢复只提交原单元，后续新计算重入 FCFS。

旧 S0/组件演示保留 atomic 模式作为兼容入口，不能把组件任务数称为最终多 Session
GPU Turn 名额；正式多 Session 执行器的 Turn 名额协议和原全部专项测试均通过。
本轮未修改 gpu.py、gpu_queue.py、compute.py，历史轨迹也与原值一致。

### C. KV / Context

模型 `bKV=2*layers*kv_heads*head_dim*element_bytes`，驻留 Session 恒满足
`K_s=bKV*Context_s`；Edge 用量由驻留 Session 求和，而不是另一可变 used 计数。
当前合法 Token 原子检查再提交，不预留隐藏输出/未来轮次。

KVBlocked 保留原完成 GPU 单元、已有 KV 和 PendingCommit，不重复计算、不提前形成
输出；真实释放触发一次合并重试，恢复按确定性局部顺序逐个检查当前容量。ContextLimit
优先于容量检查，不能加入 KV 等待绕过原生窗口。Session 终态且无活 GPU 才释放，重复
结束不重复释放；失败前已合法输出照常送达。当前没有 Shadow/迁移承诺，不伪造 S4。

### D. 流式字节与完整交付

输入 `8*n_in*btext/R_up`；输出每 Token `8*token.text_bytes/R_down`。
无线每用户独立有效速率，没有有线竞争或最终 Max-Min 分配。
Decode 与已生成下行重叠，同一 Turn 的顺序1..N不可越过。生成来源是冻结历史信息，
Turn 提交快照和 Session 当前接入不是它的替代。普通文本缓冲不混入 KV/Shadow。

### E. E2E 与未完成

`E2E=received_at-submitted_at`，由真实事件包含上传、Queue、compute、KVBlock 与下行；
不把重叠阶段时长机械相加。只在全部计划合法 Turn 正常完成时定义全量平均，否则
mean_full_turn_e2e_s=null。p95 明确为正常完成子集 nearest-rank，不能冒充全量结果。
未提交未来轮次只计离线分母，没有虚构 Turn 行、接收时刻或 E2E。

永久 KVBlocked 场景无轮询、无假移动时钟，在最后有效事件后安全静止：blocked 配置
于0.4 s结束事件推进，保留2个blocked Session和4 Byte KV，全量均值null。
这不是超时成功，也不人为释放仍存活 Session。未来 S3 有限观察窗属于周期移动的
终止设计，当前不添加假事件。

### F. 因果观察

Runtime 仅注册实际到达 Session 和已提交 Turn；Policy 只能接收 observe 构建的冻结
值白名单，不接收模拟器、事件队列、资源、Driver、Config、Seed 内部状态或离线结果。
本轮 Observation 只增加静态 Area；新 Token 对象属于已经发生的合法输出，不包含未来
输出总量，且没有向 Observation 传入其所属 Turn/Driver 引用。

新增对照：相同历史、不同隐藏输出总数/后续 Turn/私有旧 Access/未使用未来移动输入，
在0.3 s的 Observation、已发生事件、GPU rates、KV trace相同，只有一个已生成 Token。
原 Foundation/C/D 前缀隔离测试全部保留。没有实现 Mobility，因此这证明当前信息隔离
边界，不能声称已经验证未来 Markov/Handover 执行器的因果性。

### G. 所有权、导入与旧入口

没有重复类定义；相同新旧路径导出同一对象。EventQueue唯一，core与资源通过
TYPE_CHECKING/局部导入保持单一定义；30子模块全部实际导入无循环异常。
GPU work/Run 由原 GPU 拥有，Ready由原 Queue拥有，KV由 Session 及原资源原子转换
拥有，Token元数据由合法提交拥有，交付由唯一 delivered 前缀拥有。
CLI实际运行也验证没有只被测试构造、却未接入正式执行器的空实体。

## 7. 正式建模对照表

下表函数路径均位于 `src/replacement/`；测试函数位于 `tests/`。

| 建模定义 | 实体字段 | 代码文件/函数 | 运行事件 | 测试用例 | 实际结果 |
|---|---|---|---|---|---|
| ρ(e) 静态归属 | Edge.area_id | core/entities.EdgeState；Serving.__init__ | 配置创建，不随Session变化 | S1E.test_area_config_is_static_and_legacy_unspecified_is_explicit；test_invalid_explicit_area_rejected_before_serving | 显式Area-A保留；None兼容；非法ID拒绝 |
| 固定模型绑定、结构KV | ModelSpec；Session.model_id | core/entities；KV.try_commit | 入场绑定/实际提交 | Foundation.test_a_sessions_bind_distinct_models_and_independent_state；test_b_structural_kv_formula_and_validation | 4/48 Byte等结构值正确，模型不可替换 |
| 初始/实际接入独立 | initial_access_edge_id / access_edge_id | core/entities.SessionState；Driver.arrival | session_arrival | S1E.test_initial_current_and_turn_submission_access_are_distinct | 当前字段变化不改初始和提交快照、不改Execution |
| Turn提交位置是历史快照 | submitted_access_edge_id | core/runtime.submit_turn；Serving.results | turn_submit | S1E.test_multiturn_ids_zero_idle_and_snapshot_rows | 两Turn各记录E，原access列兼容快照 |
| W_s不含Mobility | TurnPlan输入/隐藏输出；私有legacy映射 | core/workload.reveal_turn | 对应Turn揭示 | S1E.test_turn_workload_contains_no_formal_access_or_mobility；test_legacy_fixed_access_loads_but_change_rejected_at_reveal | 正式无Access；旧固定值接受，变化拒绝 |
| 合法生成后才产生输出 | OutputToken | resources/kv.try_commit | token_committed/pending_committed | S1E.test_decode_records_unique_ids_and_real_generation_times | 3个ID，生成0.3/0.4/0.5 |
| 真实生成Execution/Access不可回溯改写 | OutputToken.execution_edge_id/access_edge_id | KV.try_commit | 实际合法提交 | S1E.test_runtime_commit_snapshots_actual_access_independent_of_execution；test_generation_provenance_is_frozen_after_current_access_changes | 低层提交可记录E/E2；旧Token保持原来源 |
| Blocked/失败无有效输出 | pending_commit / output_tokens | KV.try_commit / handle_event | kv_blocked→kv_retry | S1E.test_incomplete_compute_and_blocked_commit_never_publish_output；test_recovered_token_published_once_at_legal_commit_time | 恢复前无记录，3.1才生成一次，work仍8 |
| ContextLimit不产生失败输出 | completion_reason / 有效前缀 | KV.try_commit；Serving._gpu_done | context_limit | S1E.test_context_limit_only_preserves_already_legal_output；原Foundation异常测试 | 仅1合法Token，不算正常完成 |
| FIFO与唯一UE交付 | delivered前缀 / token_id | Runtime.deliver_token；Serving._start_downlink/step | downlink_start/done | S1E.test_fifo_exactly_once_delivery_uses_same_token_identity；test_delivery_rejects_wrong_identity_before_counter_mutation | 顺序1/2/3，接收1.3/2.3/3.3；重复/错ID拒绝 |
| btext与bKV分离 | Session.text_bytes_per_token / OutputToken.text_bytes | Serving上传/下行；KV结构公式 | upload_start/downlink_start | S1E.test_text_bytes_are_independent_of_structural_kv | 文本各3B，Context3/KV12B，E2E1.1 |
| |R_e|<=L_e，按Turn占名额 | 原retained GPU entry | compute.submit(continuous=True)；GPU.continue_task/release_turn | 同刻unit完成/继续/释放 | test_turn_gpu全部3项；Serving.test_b_many_units_one_slot_no_insertion_between_tokens | S1六单元仅一个entry；S2/S3在0.9/1.0开始 |
| 等权共享与部分work守恒 | GPU Fraction work/rates | resources/gpu._settle/_predict | service/shares/版本失效 | Serving.test_c_two_turn_equal_share_then_full_capacity；test_gpu守恒/细粒度测试 | 双Turn各5，剩余恢复10，无早完成/重复通知 |
| KV原子/容量/确定性恢复 | Context、SessionKV、PendingCommit | resources/kv.try_commit/handle_event | commit/block/retry/release | test_kv全部14项；Serving.test_f_natural_kv_block_recovery_no_recompute_e2e | 不超容量；恢复原单元；对应E2E1.2 |
| 恢复后新work重新FCFS | 原Queue段/累计wait | ComputeRegistry / Serving._continue | recovered→新Ready | Serving.test_recovery_next_unit_reenters_fcfs_excludes_blocked_time | queue0.1/block1.6/E2E2.4，无重算 |
| 累计Context、零Idle和最终释放 | Session.context；Turn时间 | Runtime.finish/end；Serving._maybe_finish | recv→同刻submit；session_end | Serving.test_d_multiturn_context_zero_idle_and_release；S1E多Turn ID测试 | 四Turn均值0.45；Context各4，最终KV0 |
| 完整E2E与未完成统计 | received_at/status/planned denominator | Serving.results | 最后完整交付/事件静止 | Serving.test_h_streaming_fifo_overlap_waits_for_last_output；test_g_permanent_block_and_context_failure_are_not_success | 0.5生成完仍等到3.3；blocked均值null |
| 同刻稳定/旧预测不推进时钟 | Event phase/seq/version | Serving.step/advance_to | checkpoint/gpu_completion | Serving.test_i_deterministic_same_clock_and_obsolete_predictions；test_checkpoint_processes_all_same_time_ready_events | 重复运行一致；同刻Ready全部可见 |
| 因果Observation | 只读白名单值 | core/observation.observe；私有Driver | 实际前缀 | S1E.test_future_mobility_output_and_turns_do_not_change_history；Foundation/C/D隐私测试 | 当前观察、事件、GPU/KV决定一致 |
| 唯一实体与兼容入口 | 同一class/function对象 | 根兼容模块；cli/demos | 实际导入/CLI执行 | test_package_layout；scripts/verify_s1e.py | 30模块导入成功，8演示全通过 |

## 8. 新增测试、原测试保持及真实命令

新增 `tests/test_s1e.py` 共16项：5项实体/Workload、11项Token与端到端集成。
开发先运行此模块，因缺失Area、初始快照、正式Token和TurnPlan语义得到预期失败；
接入后16项通过。没有通过删除/修改旧测试或调整历史期望数字来通过。

最后实际执行：

```powershell
python -m unittest discover -s tests -p test_s1e.py -v
python -m unittest discover -s tests -v
python scripts/verify_s1e.py
```

结果：新增16/16；全量 **110/110，OK，无失败**。原94项身份全部仍在，原8个测试文件
SHA-256与修改前完全一致；见 `s1e_original_test_ids.json`、`s1e_baseline_hashes.json` 和
`s1e_historical_trace_comparison.json`。完整逐项输出：
[新增模块](s1e_new_test_output.txt)、[全量测试](s1e_test_output.txt)。

独立审查另实际运行110项及200个固定Seed的小负载检查，核查零Idle、GPU累计work、
Token ID唯一、decode_done与记录数一致、唯一交付事件、字节分离及结果时间关联，
没有发现重要缺陷。其指出的S0 deque[int]旧注解已按实际OutputToken类型同步修正。
本轮没有遗留已知失败或未接入主执行器的实现。

## 9. 八个实际 CLI 演示回归

`scripts/verify_s1e.py` 使用子进程实际调用以下入口；PYTHONPATH只设置在子进程环境，
不会修改系统环境。每条命令、退出码、Python版本、结果位置见
[s1e_verification.json](s1e_verification.json)。所有命令 exit=0。

```powershell
python -m replacement.cli --config configs/s0_smoke.json --out <新目录>/s0
python -m replacement.gpu_demo --config configs/s1a_gpu_smoke.json
python -m replacement.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
python -m replacement.demos.kv_demo --config configs/s1c_kv_smoke.json
python -m replacement.demos.serving_demo --config configs/s1d_normal.json --out <新目录>/normal
python -m replacement.demos.serving_demo --config configs/s1d_queue.json --out <新目录>/queue
python -m replacement.demos.serving_demo --config configs/s1d_recover.json --out <新目录>/recover
python -m replacement.demos.serving_demo --config configs/s1d_blocked.json --out <新目录>/blocked
```

上面 `<新目录>` 为说明占位；一键脚本会实际生成新目录，不需要用户手填。

| 场景 | 原基准与本次实际值 | 审计 |
|---|---|---|
| S0 | 完成2，Mean0.7s，Context6，PeakKV24B，FinalKV0，结束1.4s | 全部原摘要一致；Turn CSV与历史完全一致；原事件字段/顺序一致 |
| S1-A | 2任务，work20，完成1.5/2.0s | 原摘要逐字段一致 |
| S1-B | L2/C12，3任务，work36，最后3.0s | 原摘要逐字段一致 |
| S1-C | 2轮完成、4GPU单元、work6、恢复1、KV12/0、末事件1.3s | 原摘要逐字段一致；无重算 |

| S1-D配置 | 完成/计划 | Mean E2E(s) | GPU work | Queue(s) | KVBlock(s) | Peak/Final KV(B) | 恢复单元 | 输出生成/交付 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| normal | 4/4 | 0.6 | 12 | 0 | 0 | 32/0 | 0 | 4/4 |
| queue | 4/4 | 0.6 | 12 | 0.4 | 0 | 32/0 | 0 | 4/4 |
| recover | 3/3 | 2.233333333333 | 8 | 0.1 | 2.5 | 20/0 | 1 | 5/5 |
| blocked | 0/4（只提交2轮） | null | 3 | 0.1 | 0.1（截至静止点） | 4/4 | 0 | 0/0 |

除上表外，p95、观察终点、完成率、ignored预测等全部原summary键也逐字段相等。
本地还逐层比对历史 S1-D 四场景的 summary/turns/sessions/resources/gpu_events/
kv_events/events.jsonl：每个原键、数组长度、顺序和数字完全相同，只允许新审计字段。
没有放宽浮点容差或改期望。比对结果见
[s1e_historical_trace_comparison.json](s1e_historical_trace_comparison.json)。

新完整产物保存在 `runs/s1e_20261106_150104_825969/`；先前同日验证目录及所有历史结果
均保留。一键脚本每次创建新目录，指定已存在目录会拒绝，不覆盖历史结果。
Serving输出新增 output_tokens.json；原Turn JSON/CSV、Session/资源、事件、GPU/KV及
离线config仍输出。`summary.stage=S1-D`表示Serving执行层版本，S1-E是此次最终审计，
为保持原摘要兼容没有改写执行层阶段标签。

## 10. 实际文件清单与上传

完整本轮新增/修改清单为 [S1-E_file_manifest.txt](S1-E_file_manifest.txt)。
以本轮开始时的文件哈希判定修改，不把前几轮未提交文件误记成本轮新增。

本轮修改13个已有文件：

```text
AGENTS.md
README.md
docs/model_spec/README.md
src/replacement/entities.py
src/replacement/core/entities.py
src/replacement/core/observation.py
src/replacement/core/runtime.py
src/replacement/core/workload.py
src/replacement/demos/kv_demo.py
src/replacement/demos/serving_demo.py
src/replacement/resources/kv.py
src/replacement/simulation/s0.py
src/replacement/simulation/serving.py
```

本轮新增：test_s1e.py、标准库验收脚本、此次计划/报告/清单/证据和两组共6份版本化
模型Markdown。完整逐项相对路径在清单中，不需要删除任何服务器旧文件。
GPU/Queue/Compute、全部8个旧测试和全部8份配置本轮均未改动。

Windows→Ubuntu 增量上传前提：用户已部署并验收 S1-D，按清单保持相对路径上传。
验收脚本依赖的 `docs/s1d_verification.json` 作为既有基准也列在上传清单的依赖部分。
不要只上传新测试而遗漏KV/Runtime/Serving及Workload修改。不要上传runs、缓存、环境、
私有数据、凭据、SSH配置、模型权重或joblib；没有新增第三方依赖。

Windows重跑：

```powershell
Set-Location D:\software\yxyWork\gitcode\Session
python scripts/verify_s1e.py
```

由用户完成上传后，Ubuntu验证（本轮未远程执行）：

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -p test_s1e.py -v
python3 -m unittest discover -s tests -v
python3 scripts/verify_s1e.py
```

最后一条包含上述测试及全部八个CLI，自动设置子进程PYTHONPATH并创建新目录。
预期16项新增、110项全量，八摘要相等，末行All S1 baselines unchanged。
若只查新增输出：

```bash
PYTHONPATH=src python3 -m replacement.demos.serving_demo --config configs/s1d_recover.json
```

完整stdout JSON中的output_tokens列出已生成来源和真实接收时刻；它是离线结果，不能
作为策略Observation。Git集中提交由用户另行决定，本轮没有执行。

## 11. S2 准入与未实现阶段

S1本地验收通过，没有当前已知的进入S2阻塞问题。后续开发必须继续复用当前唯一
实体/资源，不能另建一个与Serving脱离的网络演示并宣称系统已完成。

| 后续阶段 | 本轮没有实现，进入阶段时必须补齐 |
|---|---|
| S2 Network | 正式Area注册/Edge归属严格校验，有向Link/固定Path/Flow、bit/s↔Byte推进、双向配置可达性检查、无权Max-Min、FIFO唯一活动响应流、远程Serving接入 |
| S3 Mobility | 独立固定秒级检查、合法邻接Markov/私有确定性随机流、计划/实际分离、受控Turn内Handover、输入/无线Token保护、Pending/Draining、旧Access额外转发、有限观察窗 |
| S4 Migration | Source/Target/Operation、Shadow/容量承诺、Pre-copy/增量、合法STOP/Cutover、取消失败、逻辑KV复制Byte和Shadow Byte·s |
| S5及以后 | Check合并与因果策略/联合重放置、Greedy/Stay评估、真实参数及规模校准、候选PPO |

没有真实模型/硬件性能定标；当前参数继续明确为合成手算模型。1e-12 s事件网格和
Fraction GPU工作量协议沿用原实现。源码/历史轨迹留存的内存开销未作大规模压测。
这些是后续网络、移动、迁移、评估边界，**不属于已经验收的S1功能缺陷**。
