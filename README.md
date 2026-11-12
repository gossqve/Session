# Stateful AI Session Re-placement

研究移动边缘环境中有状态、多轮 LLM Session 的在线联合执行位置调整：Session 入网时固定模型，Access 与保存唯一权威 KV 的 Execution 可以不同；移动改变 Access，未来须经 KV Live Migration 与安全 Cutover 才能改变 Execution。优化目标为平均完整 Turn E2E 与综合资源 Overhead 的加权和。

S0–S3 已完成；本轮收尾后冻结 S3。Poisson 私有工作负载、S3-A Mobility、显式启用的 S3-B Handover/Draining 和 S3-C Integration 已接入同一 Serving 事件链；默认静态及 S3-A 计划模式保留。S4 尚未设计、尚未实现，S5 未开始。
资源与安全模型采用 2026-11-06 Section III（含可达性补充），优化目标采用 [2026-11-07 新 E 节](docs/model_spec/2026-11-07-weighted/Section_III_E_Problem_Formulation_加权时延与开销_精简修订稿_2026-11-07.md)，并遵循用户删除优先级/抢占/旧选择器及因果观察的覆盖。旧 E 节的仅时延目标已失效。
当前复现说明：[架构与验收入口](docs/ARCHITECTURE.md)；[文件保留与发布规范](docs/REPOSITORY_FILES.md)。

| 阶段 | 状态 |
|---|---|
| S0、S1、S2 | 完成 |
| S3-A Mobility、S3-B Handover、S3-C Integration | 完成；本轮收尾后冻结 |
| S4 KV Live Migration | 尚未设计、尚未实现 |
| S5 Joint Re-placement | 未开始 |

## 唯一正式接口

- `replacement.core.entities`：ModelSpec / SessionState / TurnState / EdgeState / OutputToken。
- `replacement.core.runtime`：RuntimeState；`core.workload` 私有负载；`core.observation` 冻结白名单快照。
- `replacement.resources`：gpu / gpu_queue / compute / kv，唯一资源实现。
- `replacement.simulation.serving`：正式多 Session、多 Turn 执行器；`simulation.s0` 保留单 Session 生命周期与安全回归。
- `replacement.demos`：gpu_demo / gpu_queue_demo / kv_demo / serving_demo。
- `replacement.cli` 是实际 S0 CLI 实现，保留。根目录的实体/资源/事件/演示转发模块已删除。

Python 3.10+，只依赖标准库。在项目根目录执行：

```powershell
python -m unittest discover -s tests -v
python scripts/verify_s1e.py
```

完整 unittest 同时执行固定回归、边界/独立 Oracle 与默认 50 个随机场景。每次未指定 Seed 时生成新的 Master Seed；输出 Master Seed、Case Seed 和场景数，失败保留配置与复现命令并直接失败，不自动换 Seed。测试使用独立临时目录，无须预建 `runs/` 或历史结果。

PowerShell 复现与扩展测试（将示例 Seed 替换为实际输出）：

```powershell
$env:SESSION_TEST_SEED = '12345'
$env:SESSION_TEST_CASES = '50'
python -m unittest discover -s tests -v
$env:SESSION_TEST_CASES = '500'
python -m unittest discover -s tests -v
Remove-Item Env:SESSION_TEST_SEED, Env:SESSION_TEST_CASES
```

独立扩展入口：`python scripts/verify_random.py --seed 12345 --cases 500 --out runs/choose_a_new_random_directory`；可加 `--case-index` 定位失败场景。
干净副本验收：`python scripts/verify_clean.py --seed 12345 --cases 50 --out runs/choose_a_new_clean_directory`，只复制白名单输入，副本不含历史 `runs/`、环境或缓存。

相同 Master Seed 复现相同场景序列，使用局部 RNG 和稳定 Seed 派生。随机测试发现实现错误；PASS 不代表算法性能或统计显著性。正式策略比较须复用相同私有外生工作负载、移动计划与共同 Seed 集合。

验收脚本先运行清理测试、S1-E 测试和全量测试，再实际运行八个 CLI，逐字段检查全部历史摘要。
每次创建新的 `runs/s1e_*` 目录，保留日志、配置、完整结果和 verification.json。

单独运行演示（PowerShell先设置 `$env:PYTHONPATH = 'src'`；Ubuntu在命令前加 `PYTHONPATH=src`）：

```bash
python -m replacement.cli --config configs/s0_smoke.json --out runs/choose_a_new_s0_directory
python -m replacement.demos.gpu_demo --config configs/s1a_gpu_smoke.json
python -m replacement.demos.gpu_queue_demo --config configs/s1b_gpu_queue_smoke.json
python -m replacement.demos.kv_demo --config configs/s1c_kv_smoke.json
python -m replacement.demos.serving_demo --config configs/s1d_normal.json
python -m replacement.demos.serving_demo --config configs/s1d_queue.json
python -m replacement.demos.serving_demo --config configs/s1d_recover.json
python -m replacement.demos.serving_demo --config configs/s1d_blocked.json
```

## 当前语义

Admission时固定模型；结构公式派生KV Byte/token。Context累计跨Turn；逐Token实际合法提交才增长Context/KV。
GPU按Turn占并发名额，FCFS进入、动态Equal-Share；连续Prefill/Decode保留资格，KVBlocked释放资格。
Pending恢复不重算，后续新计算重新FCFS。底层atomic API仍用于真实的资源验证/S0，不是第二套调度器。
完整响应按FIFO送达后Turn才完成；下一轮同刻提交。E2E直接取接收减提交，不重复累计重叠时段。
G1 对应 `mean_full_turn_e2e_s`：全部计划合法 Turn 均有真实完整交付时刻时，以全部计划合法 Turn 数为分母计算；有未完成 Turn 或空负载则为 null。合法零输出完成计入。`mean_completed_full_turn_e2e_s` 和 p95 仅为正常完成子集诊断，不能替代 G1。完成率、未完成/未提交数量、KVBlocked、删失时长及原因分别报告，不赋零时延或伪造完成。

当前目标为 `ω1·D̄_E2E + ω2·(β_mig·V_mig + β_sh·A_shadow + β_HO·V_HO)`。
`V_mig` 是实际逻辑 KV Copy Byte，`A_shadow` 是已物化 Shadow KV 的 Byte·s，`V_HO` 是额外普通响应转发阶段实际传输的逻辑 Byte。各项独立记账，不按路径跳数放大，取消/失败前已发生的成本保留；未物化承诺不计 Shadow，竞争和冻结等待通过真实 E2E 反映。
权重、折算系数和单位尺度尚未确定，不设置默认值、归一化方案或综合分数。当前 S3 没有实际 KV Copy/Shadow，对应开销如实为零；这不表示 S4 已实现。

无拓扑时固定 Access=Execution；显式拓扑支持固定远程 Serving。无线每用户独立有效速率。无 H/L 服务优先级、抢占、内部模型选择器。
EventQueue.priority 仅表示同刻事件处理阶段。GPU 为 Turn 级 FCFS/Equal-Share，有线共享使用无权 Max-Min。S3-A 的独立时间 Markov 计划/Pending、S3-B 的受保护实际 Handover/串行 Draining 和 S3-C 综合验收均已完成。Handover 只改 Access，不改变 Execution、权威 KV 或已生成 Token 来源。
合成参数用于手算验证，不是实际硬件性能或论文实验结果。

## 数据与配置边界

- Session `initial_access_edge_id` 是不可变入网快照，`access_edge_id` 是当前实际接入。
- Turn只使用 `submitted_access_edge_id` 表示提交快照，已删除旧结果 `access_edge_id` 别名。
- OutputToken的`access_edge_id`/`execution_edge_id`表示合法生成时的真实来源，生成后不可改写。
- `RuntimeState.deliver_token(session_id, token_id=(session_id, turn_index, output_index))` 必须显式提供身份。
- TurnPlan仅有input_tokens/hidden_output_tokens。JSON中任何Turn含access_edge_id都在加载时ValueError，即使等于初始Access。
- Edge.area_id静态；None明确表示未配置区域，S2正式拓扑必须严格验证归属，不假造Area。
- 只有私有Driver/离线评价能查看完整工作负载；在线只接收冻结Observation，不能持有Driver/Config/未来事件引用。

## 结果与历史记录

Serving输出Turn JSON/CSV、Session/resource、OutputToken、事件JSONL、GPU/KV事件和离线config。
文本Byte与结构KV Byte独立记账；交付唯一权威状态为Turn.delivered前缀。

当前服务器白名单：[server_files.txt](release/server_files.txt)。
当前 GitHub 白名单：[github_files.txt](release/github_files.txt)。
本地检查和打包：`python scripts/prepare_release.py --target server --package`，只产生新的本地 ZIP，不执行同步。
历史阶段上传/删除清单只作本地档案，当前发布不再依赖它们。
当前模型：[model_spec README](docs/model_spec/README.md)。
Foundation/C/D/E报告、旧上传清单和历史runs保留为阶段档案，其中旧命令/兼容条款不再是当前接口要求。
不上传缓存、凭据、环境、权重或runs；本地代理不执行SSH/SCP或Git提交/同步。

## S2-A 静态拓扑与可达性

正式实体位于 `replacement.network.entities`；唯一管理对象位于 `replacement.network.topology.NetworkTopology`。
Area边界是非服务节点，Edge仍复用core.entities.EdgeState。S2参与Edge必须明确area_id；S1未指定Area的配置不受影响。
跨区域固定路径为Edge→本域边界→目的域边界→目的Edge；不自动寻路、补反向链路或经过第三域。

```powershell
python -m unittest discover -s tests -p test_topology.py -v
$env:PYTHONPATH = 'src'
python -m replacement.demos.topology_demo --config configs/s2a_topology_smoke.json
```

生产调用：`NetworkTopology.from_config(config, edges=runtime.edges.values())`；加载时验证所有链路、路径、显式允许的双向Serving组合与可能移动转移。
邻接不代表有线路径；未来传输应复用同一拓扑对象及只读links/paths，不能另建独立拓扑。
S2-A 子模块只负责静态拓扑；Flow/字节推进与共享分别由 S2-B/C 实现，Markov 与 Handover 由 S3-A/B 实现。
完整复现说明见 [ARCHITECTURE](docs/ARCHITECTURE.md)，阶段报告仅本地归档。

## S2-B Flow、字节推进与远程Serving

`network.runtime.NetworkRuntime`复用同一EventQueue，Flow快照不可变；G/Y按Fraction真实推进，bit/s除以8换Byte。
`WirelessRuntime`复用同一推进内核，每Session/方向独立，替换正式Serving原有固定时长调度；不参与有线公平分配。
S2-B阶段Disjoint分配器仅允许正待发Flow路径不共享有向Link，现仅在显式历史模式抛S2CRequired；正式默认已改为下节S2-C Max-Min。

启用方式：Serving配置增加`topology`（S2-A schema），其edges必须与顶层已有EdgeState一致。
准入检查允许组合成员资格、模型部署和独立双向可达性。无线完整上传后转有线Prompt，输入完整到Execution才Ready；
合法输出追加同一Turn持续Response Flow，到达累计Token边界才进入无线FIFO。Flow暂空等待数据，正式生成结束才关闭生产者。

```powershell
python scripts/verify_s2b.py
$env:PYTHONPATH = 'src'
python -m replacement.demos.serving_demo --config configs/s2b_remote.json
```

五个配置：s2b_local / remote / pipeline / disjoint / conflict。最后一个是S2-C阶段边界反例，预期拒绝。
脚本在新的runs/s2b_*保存逐项日志和场景数据，同时运行原S1验收和S2-A Demo。
输出新增network_flows.json、network_events.jsonl、wireless_transfers/events，以及Token有线到达/无线开始/实际接收时间。

无线方向可直接给`wireless_up_bits_per_second`，或给`wireless_up={bandwidth_hz,snr_linear,efficiency}`（down同理）；
同一配置作用域不能同时给两种表示。Session可按方向覆盖全局表示。更新速率先结算已有Byte，不重传。
构造`ServingSimulator(config, network_allocator=...)`可为S2-C注入分配器；内核仍校验所有有向Link总容量。
复现说明：[ARCHITECTURE](docs/ARCHITECTURE.md)；S2-B 阶段报告仅本地归档。

## S2-C 正式共享网络默认

启用topology的Serving与NetworkRuntime默认使用`network.max_min.MaxMinAllocator`。
它从零同时增长未冻结Flow，遇饱和Link冻结相关Flow，保留冻结Flow对整条路径的占用并继续回收剩余容量；
不是逐链路一次均分。速率和残余容量内部用Fraction，所有有向Link逐次检查容量。无线不参与此分配。

```powershell
python scripts/verify_s2c.py
$env:PYTHONPATH = 'src'
python -m replacement.demos.serving_demo --config configs/s2c_maxmin_three_area.json
```

配置：s2c_maxmin_shared、pipeline、three_area、wide。wide仅把六条跨域Link容量乘4，复用相同外生负载。
每次分配在原network_events.jsonl输出原因、Flow G/Y、前后速率和逐Link容量/负载/余量/利用率。
verify_s2c从同一轨迹导出flow_rates/link_utilization/flow_bytes三份JSONL视图，不建立另一套资源账本。
独立Oracle使用有理数线性方程枚举有序可行区域顶点，和正式渐进填充实现分离。

S2-B历史拒绝反例现在必须显式选择`--allocator disjoint`；verify_s2b已这样指定，其他场景使用正式Max-Min默认。
旧S2-B文档中的“默认拒绝共享”仅为阶段历史。正的外部rate_limit仅是既有传输速率上限，不是业务权重；0表示显式暂停。
复现说明：[ARCHITECTURE](docs/ARCHITECTURE.md)；S2-C 阶段报告仅本地归档。

S3-A 验收：`python scripts/verify_s3a.py`；仅生成计划与 Pending，不切换实际 Access。具体输出和边界见 [ARCHITECTURE](docs/ARCHITECTURE.md)。

Poisson 综合验收：`python scripts/verify_workload.py`。配置为 `configs/poisson_session_smoke.json`；真实 KV Copy/Cutover 未实现，仅提供单在途 Migration Admission Guard。参数、复现与信息边界见 [ARCHITECTURE](docs/ARCHITECTURE.md)。

S3-C 全局验收：`python scripts/verify_s3c.py`。复用 S1/S2/S3-A/B 验收链，增加三 Session 手算综合配置、资源轨迹守恒审计和离线删失/额外转发指标；详见 ARCHITECTURE 的 S3-C 章节。输出仅保存至新的 `runs/` 目录，不执行发布或服务器操作。
