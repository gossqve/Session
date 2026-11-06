# Stateful AI Session Re-placement

当前状态：S1 完成实体、GPU、KV、多 Session/多 Turn Serving 与最终旧代码清理。
建模依据是 2026-11-06 Section III（含可达性补充）、用户删除优先级/抢占/旧选择器的覆盖，以及本次最终清理要求。
当前完整说明：[S1 cleanup report](docs/S1_cleanup_report.md)。

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
有任意计划Turn未正常完成时，全量平均E2E为null；p95明确为正常完成子集。

S1固定Access=Execution，无线每用户独立有效速率。无H/L服务优先级、抢占、内部模型选择器。
EventQueue.priority仅表示同刻事件处理阶段。未实现S2有向网络/Max-Min、S3独立秒级Markov/Handover、S4迁移、后续策略/PPO。
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

本次新增/修改：[S1_cleanup_changed_paths.txt](docs/S1_cleanup_changed_paths.txt)。
应从服务器删除的旧文件：[S1_cleanup_deleted_paths.txt](docs/S1_cleanup_deleted_paths.txt)。
一次同步S1-E加本轮清理的上传清单：[S1_cleanup_sync_paths.txt](docs/S1_cleanup_sync_paths.txt)。
当前模型：[model_spec README](docs/model_spec/README.md)。
Foundation/C/D/E报告、旧上传清单和历史runs保留为阶段档案，其中旧命令/兼容条款不再是当前接口要求。
不上传缓存、凭据、环境、权重或runs；本地代理不执行SSH/SCP或Git提交/同步。
