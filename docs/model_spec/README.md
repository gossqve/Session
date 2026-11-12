# 当前正式建模与历史材料索引

更新：2026-11-12。S0、S1、S2、S3-A Mobility、S3-B Handover、S3-C Integration 已完成，本轮收尾后冻结 S3；S4 KV Live Migration 尚未设计、尚未实现，S5 Joint Re-placement 未开始。当前接口、测试和复现入口见 [ARCHITECTURE](../ARCHITECTURE.md)，发布规则见 [REPOSITORY_FILES](../REPOSITORY_FILES.md)。阶段报告、旧命令和历史运行结果不是测试依赖。

## 权威顺序与当前覆盖

1. 用户最新任务与本索引登记的覆盖优先：无 Session H/L、GPU 抢占或旧 R2A 选择器；模型在 Admission 配置绑定；在线只使用当前和历史信息；禁止任何 per-Turn Access 配置。完整计划、未来 Turn/输出/移动、观察终点和事件队列不进入在线 Observation。
2. **优化目标采用 [2026-11-07 加权 Section III.E 原稿](2026-11-07-weighted/Section_III_E_Problem_Formulation_加权时延与开销_精简修订稿_2026-11-07.md)。** 它替代 2026-11-06 E 节及历史材料中“仅最小时延、开销只作辅助”的目标文字，也覆盖旧 A 节概述中的对应表述。此前将完成者子集均值称为 G1 的口径已撤销。
3. 资源、网络、Mobility、Handover 与状态安全机制继续采用 [2026-11-06 含可达性补充的主文 A–D](2026-11-06-reachability/Section_III_完整中文系统建模_最终核查修订版.md)，并应用上述用户覆盖。主文的迁移描述是未来研究机制，不表示代码已实现 S4。
4. [开发建模注意.md](开发建模注意.md) 保留为分阶段开发规范和历史来源；其旧阶段进度、逐轮 Access、旧兼容接口及服务器操作建议服从本索引和用户最新限制，不构成本地代理执行远程/Git 操作的授权。
5. 各版本的公式依据表和一致性检查报告只作辅助核对，不能证明当前实现完成或测试通过。其余旧文档按下方历史索引使用。

## 当前目标与完整交付口径

令 `Q_all` 为共同外生工作负载中的全部计划合法 Turn。完整 Turn E2E 为真实完整接收时刻减提交时刻：

\[
D_q^{\mathrm{E2E}}=t_q^{\mathrm{recv}}-t_q^{\mathrm{sub}}.
\]

它覆盖实际 Prompt 上传/转发、GPU 等待与计算、KVBlocked、响应交付、Handover 接续和未来迁移冻结等待；计算与流式传输可能重叠，不能直接累加阶段时长。合法零输出按合法零载荷结束事件完成。

仅在全部计划合法 Turn 均有真实完整交付时刻时，计算

\[
\overline D^{\mathrm{E2E}}=\frac{1}{|Q_{\mathrm{all}}|}
\sum_{q\in Q_{\mathrm{all}}}D_q^{\mathrm{E2E}}.
\]

**G1 对应 `mean_full_turn_e2e_s`，使用全量计划合法 Turn 分母；未全部完成或空负载时为 null。** `mean_completed_full_turn_e2e_s` 和完成者 P95 仅供诊断，不能替代主目标。未完成运行须分别报告完成率、未完成/未提交数量、KVBlocked、删失时长和原因；不能赋零、伪造完成或按各算法结果删去困难样本。完整交付子集是目标定义域，不能据此强制恢复。

当前联合优化方向为

\[
\min_{\pi\in\Pi_{\mathrm{safe,full}}}
\mathbb E_{\omega}\left[
\omega_1\overline D^{\mathrm{E2E}}(\pi;\omega)
+\omega_2 C(\pi;\omega)\right],
\]

\[
C=\beta_{\mathrm{mig}}V^{\mathrm{mig}}
+\beta_{\mathrm{sh}}A^{\mathrm{shadow}}
+\beta_{\mathrm{HO}}V^{\mathrm{HO}}.
\]

- `V_mig`：实际逻辑 KV Copy Byte；`A_shadow`：已物化 Shadow KV 的累计 Byte·s；`V_HO`：额外普通响应转发阶段实际推进的逻辑 Byte。
- 三项独立输出，保留失败/取消前成本和观察截止前的部分传输；不按有线路径跳数重复计量，不把未物化承诺当 Shadow，不重复叠加已经进入 E2E 的竞争/冻结时长。
- `ω1`、`ω2`、各 `β` 和单位折算尺度尚未确定；不设默认权重、正式归一化或综合分数。当前 S3 没有实际 KV Copy/Shadow，对应开销如实为零，并标明 S4 未实现。
- 正式算法比较复用同一外生 WorkloadPlan、Markov 移动输入和共同 Seed 集合；实际 Handover 时刻可因保护/服务过程而不同。随机测试 PASS 仅验证实现，不代表策略性能或统计显著性。

## 实现与阶段边界

| 阶段 | 当前状态与机制 |
|---|---|
| S0 | 完成；保留单 Session 生命周期、安全和手算回归 |
| S1 | 完成；canonical core/resources/simulation/demos，Turn 级 GPU 名额/FCFS/Equal-Share、累计 Context、原子 KV 提交/阻塞/恢复、零 Idle、完整 E2E |
| S2 | 完成；唯一 NetworkTopology、固定有向路径、真实 Flow/Byte 推进、无权 Max-Min、独立无线 FIFO、固定远程 Serving |
| S3-A Mobility | 完成；私有到达相对 Markov 计划、Pending FIFO、有限 T_obs 和生命周期取消，计划模式不改实际 Access/Execution |
| S3-B Handover | 完成；显式启用实际 Access 切换、Prompt/无线 Token 保护与串行 Draining；Execution/权威 KV/已生成 Token 来源不变 |
| S3-C Integration | 完成；统一事件链、共享资源/Token/Byte 审计与离线评价；本轮收尾后冻结 S3 |
| S4 KV Live Migration | 尚未设计、尚未实现；现有 MigrationAdmissionGuard 只是单 Session 固定 Source/Target 准入租约 |
| S5 Joint Re-placement | 未开始 |

完整 unittest 保留固定回归、独立 Oracle 与边界检查，并默认运行 50 个合法随机场景；未指定 `SESSION_TEST_SEED` 时产生新 Master Seed，指定后稳定复现。`SESSION_TEST_CASES` 默认 50，扩展验证至少 500；记录 Master/Case Seed、失败配置与复现命令，失败不得忽略或换 Seed。测试不依赖预先存在的 `runs/`、历史结果或执行顺序。

## 原稿来源、完整性与交叉引用

新 E 原稿从用户本机 `C:/Users/71968/Desktop/Section_III_E_Problem_Formulation_加权时延与开销_精简修订稿_2026-11-07.md` 按原始字节复制。任务所写文件名带 `(1)`，实际找到的原稿不带该后缀；未伪造或改写正文。

```text
7257 bytes
SHA-256 1c3865b71f4415fe36c2e7fe9e74c5be23153d66bfa09cac382faa30dd993290
```

新 E 使用独立编号 (14)–(20)，并引用 D(12)/(13)；现有完整主文对应尾部准入/原子切换为 D(29)/(31)，完整 E2E 为 C(22)。这是来源版本的编号不一致，当前按章节语义对照，保留原稿并待论文合稿时统一，不据此改动资源数学模型。两份 2026-11-06 完整主文只在 E 标题后新增过时标记，A–D 与其余原文保持原字节。

## 历史材料索引

| 路径 / 材料 | 性质与适用范围 |
|---|---|
| `2026-11-06-reachability/` | 当前 A–D 资源/安全依据；E 已被新稿替代。主文补充移动后 Access/原 Execution 双向可达性预检 |
| `2026-11-06-final/` | 前一版整合稿及核对附件；E 已过时，可达性采用上项补充 |
| `Stateful_AI_Session_Re-placement_Section_III_完整中文系统建模.md` 及同目录核对表/报告 | 2026-11-03 整合历史来源，来自用户桌面 `Section_III_完整整合与核查_2026-11-03.zip`；旧优先级/抢占/仅时延文字均不覆盖当前规范 |
| `开发建模注意.md` 中 S1–S7 路线、旧阶段记录与本地阶段报告 | 开发历史和来源；旧阶段状态、逐轮移动、根转发兼容及同步命令均不能作为当前接口规则 |
| `docs/` 下 S1/S2/S3 阶段审计、上传清单；`runs/` 历史结果 | 只在本地保留，不批量重写，不作为运行或测试依赖；正式 fixture `docs/s1d_verification.json` 特例保留 |

2026-11-03 三份历史 Markdown 原始 SHA-256 保留如下；本轮不修改这些文件：

```text
09703aa449639012986b92a8a57cdd7472af770f9b8daadfc281f93a9afa8440  Stateful_AI_Session_Re-placement_Section_III_完整中文系统建模.md
cd438e6cb7f866bd3d027a5dc7601880c18b17f50323448610d9af0b37f01916  Section_III_公式与参考文献依据核对表.md
11af5cf4e9077c65f2464e3ccb305c030d2f220274c94be4306aa606e381c91d  Section_III_最终一致性检查报告.md
```