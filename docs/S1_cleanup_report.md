# S1 最终旧代码清理与全量验收报告

日期：2026-11-06；仅在 Windows 本地 `D:\software\yxyWork\gitcode\Session` 操作。

结论：清理完成，118项测试通过，八个实际CLI演示全部原摘要一致。没有已知阻止进入S2的S1功能问题。S1-E尚未上传服务器，本报告提供S1-E加本轮清理的一次同步清单；本轮没有SSH/SCP、服务器操作、Git提交/同步/重置或全局环境修改，没有覆盖历史runs。

## 1. 审查范围与采用依据

采用用户本次最终清理要求、2026-11-06 Section III（含可达性补充）、S1-E实体/资源审计和开发建模注意。用户要求优先于历史兼容条款；源建模文件中的H/L、抢占、内部模型选择器不属于当前实验。

逐文件检查当前21份src Python、10份测试、8份配置、1份脚本，以及README、AGENTS和模型入口。完整AST/配置清单和类定义归属在[S1_cleanup_audit.json](S1_cleanup_audit.json)。所有源码类定义唯一；全部20个子模块实际导入成功。源码检查追踪了legacy/deprecated、逐轮Access、转发、别名、交付调用、priority/preempt/R2A和资源所有权；没有仅按关键词删除。

## 2. 真正删除的旧接口与调用迁移

| 原位置/旧行为 | 决定及理由 | 现在的唯一接口/受影响调用 |
|---|---|---|
| 根目录compute/entities/events/gpu/gpu_demo/gpu_queue/gpu_queue_demo/observation/s0/workload.py | 删除10个纯转发文件，没有第二份实现但会延长过时入口生命周期 | 所有仓库测试改用core/resources/simulation/demos；脚本改用demos.gpu_demo和demos.gpu_queue_demo |
| core/workload.py::_legacy_turn_access、legacy_turn_access构造参数、_legacy_access | 删除逐轮Access私有兼容映射，不再把Turn作为位置计划载体 | S0和Serving加载器统一_validate_turn_schema；任何Turn含access_edge_id，包含相同值或null，都在加载时ValueError |
| reveal_turn中的旧Access比较/延迟NotImplemented | 删除；未来位置不属于正式Turn工作负载 | RevealedRequest只揭示输入；TurnPlan仅input_tokens/hidden_output_tokens |
| Runtime.deliver_token(session_id)默认交付下一个输出 | 删除隐式参数默认和条件绕过分支 | 必须deliver_token(session_id, token_id=(sid,turn,index))；None/错ID/跨Turn/重复/越序拒绝；缺参TypeError |
| Serving.results Turn行access_edge_id别名 | 删除，与submitted_access_edge_id重复且易误解为整轮恒定位置 | Turn JSON/CSV只保留submitted_access_edge_id；Session.access_edge_id和OutputToken.access_edge_id含义各自保留 |
| kv_demo隐式交付 | 迁移；脚本化恢复验证仍有真实用途 | 生成合法Token后把同一token_id放入交付事件，事件消费显式传ID |
| package __init__“Only S0”说明、README旧命令/兼容描述、AGENTS旧兼容要求 | 更新为当前正式入口，避免新增代码照旧规则实现 | README当前接口、模型索引覆盖声明、本报告 |

删除的仅是10个文件，路径逐项见[S1_cleanup_deleted_paths.txt](S1_cleanup_deleted_paths.txt)：相对仓库根目录、一行一个文件、无目录/绝对路径/`..`。没有删除任何正式实体或资源实现。

当前负载格式不支持任何按Turn预设Access。加载阶段检查无效schema是配置合法性检查，不是预测未来Context/KV或服务结果。未来信息隔离样本必须使用合法格式，不能把本应拒绝的旧配置作为因果性样本。

## 3. 明确保留的有用实现

- 原EqualShareGPU、GPUQueue的atomic API：S1-A/B资源手算、边界、取消、部分work守恒和S0组件路径真实使用。它们是同一个资源引擎的粒度接口，不是旧优先级调度器。连续多Session Serving仍使用continuous=True，按Turn保留名额。
- GPU withdraw/cancel：仅显式组件退出/取消接口及专项测试使用，未接入H/L抢占或任何自动策略；取消不等于KVBlocked恢复。
- simulation/s0.py及replacement.cli：前者仍提供原生命周期、安全/Context/流式回归；后者是实际CLI实现，不是转发模块，所以保留。
- demos/kv_demo.py：用真实Model/Session/Turn/compute/KV和原Pending事件验证恢复，不是另一个KV引擎；合成交付延迟只用于资源验证，不称完整共享网络。
- EventQueue.priority：同刻事件阶段顺序，与Session服务优先级无关。删除它会破坏确定性处理，故保留并保留稳定顺序测试。
- Session初始/当前Access、Turn提交快照、冻结OutputToken：都是不同时间语义，不能机械合并。Edge.area_id=None明确未指定；S2再严格验证注册表。
- OutputLengthLimit、ContextLimit、KVBlocked、重试版本/去重、GPU旧预测失效、同刻retained边界、安全终态释放、全部计量与E2E逻辑：继续保留。

resources/gpu.py、gpu_queue.py、compute.py、kv.py均未改变算法/状态来源。KV仍是Session权威字节，Edge占用派生求和；GPU运行集合和工作量仍是原引擎；交付仍只有Turn.delivered前缀，没有第二份Token ledger。

源码不存在H/L调度、抢占策略、R2A选择器或旧Turn边界移动规则。剩余legacy文字属于拒绝旧字段的错误说明、未配置Area语义和历史基准JSON组名，不是兼容执行分支。禁止priority输入的测试继续保留，不因为关键词清理而删除拒绝机制。

## 4. 精确schema/入口迁移

| 原调用或输出 | 当前要求 |
|---|---|
| replacement.entities.ModelSpec等 | replacement.core.entities；RuntimeState单独来自core.runtime |
| replacement.events / s0 | replacement.simulation.events / s0 |
| replacement.gpu / gpu_queue / compute | replacement.resources.gpu / gpu_queue / compute |
| replacement.observation / workload | replacement.core.observation / workload |
| python -m replacement.gpu_demo / gpu_queue_demo | python -m replacement.demos.gpu_demo / gpu_queue_demo |
| JSON session.turns[*].access_edge_id | 移除该字段；Session级初始access_edge_id保留；不再有兼容加载 |
| TurnPlan第三个Access参数 | 已在S1-E移除，本轮补充明确拒绝测试 |
| deliver_token(sid) | deliver_token(sid, token_id=已生成Token.token_id) |
| Turn结果access_edge_id | submitted_access_edge_id；该列是提交快照 |
| Session/OutputToken结果access_edge_id | 保留；分别是当前接入和实际生成时接入，不是别名 |

除Turn结果移除一个别名外，所有服务/资源数值和其他原结果字段保持原值。验收脚本不补回该列、不放宽数值预期；全部原summary键逐字段精确比较。历史D四场景的Turn明细、资源、Session、GPU/KV事件与完整事件轨迹也逐键/顺序比对通过，只排除明确删除的Turn别名，证据在审计JSON。

## 5. 测试变更逐项说明

数量：**110 - 2个旧测试身份 + 3个替换测试 + 7个新增测试 = 118项**；原108个其他测试身份保留。没有删除工作量、GPU名额、显存、流式交付、Context或因果性断言。

两个替换点：

1. test_package_layout.test_legacy_and_canonical_imports_share_definitions替换为两个测试：test_canonical_definitions_unique_and_importable（全部canonical导入与类定义唯一）和test_removed_forwarding_modules_are_not_importable（10旧入口不存在）。保留“不存在两套实体”的安全目的，并切换为当前入口契约。
2. test_s1e.test_legacy_fixed_access_loads_but_change_rejected_at_reveal替换为test_per_turn_access_is_rejected_for_all_turns：当前/后续轮次的相同Access也必须加载失败，不再测试旧兼容接受行为。

新增tests/test_cleanup.py共7项：

| 测试 | 实际安全覆盖 |
|---|---|
| test_turn_access_rejected_even_when_equal_to_initial | Serving逐轮Access相同/不同/null一律拒绝 |
| test_s0_future_turn_access_rejected_at_loading | S0未来轮旧schema也不能静默执行 |
| test_delivery_requires_explicit_nonnull_identity_without_mutation | 缺ID和None均拒绝且交付计数不变，之后真实Serving仍完成 |
| test_turn_result_has_only_unambiguous_submission_access | 删除Turn别名，Session与Token真实字段保留 |
| test_rejected_turnplan_access_argument | 三参数TurnPlan不能恢复 |
| test_repeated_commit_does_not_duplicate_output_identity | 正式路径重复提交拒绝，输出身份不重复 |
| test_future_arrival_access_does_not_change_prefix | 两份合法多Edge样本，未来Session不同Access/Execution，当前Observation/事件/GPU/KV前缀相同 |

原Foundation/KV/Serving/S1-E因果样本中的旧per-Turn Access移除，仍比较不同未来隐藏输出/轮数/到达，所有快照和资源断言保持。新的future_arrival测试补充合法初始位置差异；S1尚无Mobility采样器，不虚构未来移动执行测试。

Foundation、GPU、Queue、S0测试只迁移导入；Foundation/KV交付辅助调用改为当前Token的显式ID，原生命周期/安全断言保留。所有修改/新增测试身份清单及原110到118的差分在审计JSON中。

## 6. 真实运行结果

实际执行：

```powershell
python -m unittest discover -s tests -p test_cleanup.py -v
python -m unittest discover -s tests -v
python scripts/verify_s1e.py
```

清理测试初始捕获缺少schema拒绝、隐式交付和输出别名等预期失败；修改后全部通过。
最终完整unittest：**Ran 118 tests，OK**。脚本依次运行清理7项、S1-E16项、全量118项，再实际运行八个CLI和canonical导入，全部exit=0。

结果目录：`runs/s1e_20261106_170243_261471/`。先前目录全部保留。
[全量逐项日志](S1_cleanup_test_output.txt)、[清理模块日志](S1_cleanup_new_test_output.txt)、[命令/退出码/全部摘要](S1_cleanup_verification.json)。

| 演示 | 实际回归结果 |
|---|---|
| S0 | 完成2Turn，Mean0.7s，Context6，KV峰值24B，最终0，结束1.4s |
| S1-A | work20，完成时刻1.5/2.0s |
| S1-B | work36，最晚3.0s完成 |
| S1-C | work6，4个唯一GPU单元，恢复1，KV峰值12B，最终0，无重复计算 |
| D normal | 4/4，Mean0.6s，work12，Queue0，Block0，KV32/0B |
| D queue | 4/4，Mean0.6s，work12，Queue0.4s，Block0，KV32/0B |
| D recover | 3/3，Mean2.233333333333s，work8，Queue0.1s，Block2.5s，恢复1，KV20/0B |
| D blocked | 0/4，Mean null，work3，Queue0.1s，事件静止0.4s，保留KV4B |

GPU Turn连续不插队的3个专项测试及Serving多单元测试、Fraction工作量与旧事件测试全部通过；KV恢复/不重算/容量测试、模型不可变/部署兼容、FIFO及完整响应才完成、零Idle、全部因果观察测试均通过。不是仅以测试数量代替实际演示与状态/事件审查。

## 7. 全部文件变更及一次同步

本轮新增/修改逐项清单：[S1_cleanup_changed_paths.txt](S1_cleanup_changed_paths.txt)。
本轮删除逐项清单：[S1_cleanup_deleted_paths.txt](S1_cleanup_deleted_paths.txt)。
用于服务器尚未收到S1-E的完整上传集合：[S1_cleanup_sync_paths.txt](S1_cleanup_sync_paths.txt)。它包含当前所有src/tests/configs/scripts、S1-E新增模型/报告/证据和本轮说明；不会引用已经删除的本地转发文件。旧S1-E“32文件包”不适用于本轮最终同步，不能再用它恢复旧代码。

清理前哈希：[S1_cleanup_baseline_hashes.json](S1_cleanup_baseline_hashes.json)。所有8配置保持不变，所有模型原文、历史runs均保留。完整新增/修改路径在清单中，包括AGENTS、README、模型入口、验收脚本与测试导入的修改。

建议用户一次同步流程：

1. 暂停服务器同一源码的独立编辑，备份将覆盖和删除的文件。
2. 按新的sync_paths以相对目录上传当前文件（含S1-E），不上传runs、环境、缓存、凭据/SSH配置、权重、joblib。
3. 根据deleted_paths移除服务器上的10个**指定文件**。先校验每行相对路径、无`..`、目标解析仍在项目内且为普通文件；只删除名单文件，不递归删除目录。仅SCP新增覆盖不足以完成本轮清理。
4. 在VS Code远程终端运行下面命令。没有通过前不应把S1-E或本次清理记作Ubuntu验收完成。

```bash
cd /mnt/data2/users/yxy/llmwork/session
python3 -m unittest discover -s tests -v
python3 scripts/verify_s1e.py
```

预期118项通过，八CLI全部exit=0，末行All S1 baselines unchanged。
脚本自动使用src作为子进程PYTHONPATH，不修改系统环境、不安装包；每次新目录保存完整结果。
删除旧入口的测试能发现服务器漏删转发文件；模块导入和全部CLI能发现上传遗漏。

本轮没有执行远程同步或Git操作；最终集中Commit/Push仍由用户另行决定。

## 8. 阶段结论

当前运行代码无逐轮移动兼容分支、根目录转发、隐式交付或含糊的Turn Access别名；没有H/L、抢占或旧内部选择器的可执行逻辑。剩余atomic接口和阶段演示各有实际资源/生命周期验证用途，已在报告解释，不能为了减少文件而删除。

S1本地全量验收通过。S2有向网络/Max-Min/正式Area校验、S3独立秒级Markov/Turn内受控Handover/保护及Draining、S4迁移/Shadow/Cutover、策略/PPO仍未实现，不伪装为S1功能或缺陷。所有后续模块必须继续扩展本套唯一实体、资源与事件链。

## 9. 本轮逐项文件账目

修改18个已有文件：

```text
AGENTS.md
README.md
docs/model_spec/README.md
scripts/verify_s1e.py
src/replacement/__init__.py
src/replacement/core/runtime.py
src/replacement/core/workload.py
src/replacement/demos/kv_demo.py
src/replacement/simulation/serving.py
tests/test_foundation.py
tests/test_gpu.py
tests/test_gpu_queue.py
tests/test_kv.py
tests/test_package_layout.py
tests/test_s0.py
tests/test_s1e.py
tests/test_serving.py
tests/test_turn_gpu.py
```

新增10个文件：

```text
docs/S1_cleanup_audit.json
docs/S1_cleanup_baseline_hashes.json
docs/S1_cleanup_changed_paths.txt
docs/S1_cleanup_deleted_paths.txt
docs/S1_cleanup_new_test_output.txt
docs/S1_cleanup_report.md
docs/S1_cleanup_sync_paths.txt
docs/S1_cleanup_test_output.txt
docs/S1_cleanup_verification.json
tests/test_cleanup.py
```

删除10个转发文件：

```text
src/replacement/compute.py
src/replacement/entities.py
src/replacement/events.py
src/replacement/gpu.py
src/replacement/gpu_demo.py
src/replacement/gpu_queue.py
src/replacement/gpu_queue_demo.py
src/replacement/observation.py
src/replacement/s0.py
src/replacement/workload.py
```

完整一次同步集合共70个现有文件；删除清单单独处理，不把删除路径当作上传文件。
