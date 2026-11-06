# 当前正式建模与历史材料索引

2026-11-06：S1最终清理要求优先于下方历史S1-E接口描述。

当前代码只使用canonical子包；旧根目录转发模块已删除。任何per-Turn Access配置加载即拒绝，不再保留兼容映射。
Turn结果仅用submitted_access_edge_id；交付必须显式token_id。Session初始/当前Access与Token生成来源保持独立。
固定模型在Admission配置绑定，禁止H/L、抢占、旧R2A选择逻辑；在线不得查看未来Turn/输出/移动。

当前主文：[2026-11-06含可达性补充](2026-11-06-reachability/Section_III_完整中文系统建模_最终核查修订版.md)。
完整清理与验收：[S1_cleanup_report.md](../S1_cleanup_report.md)。
`开发建模注意.md`及下列版本记录保留原阶段历史；其中逐轮移动、兼容接口、服务器操作建议等与用户当前要求冲突的条款不执行。
未来Mobility按独立固定秒级检查和邻接Markov产生，可在Turn内合法Handover；S1不实现该运行机制。

---

以下为S1-E阶段登记档案（兼容映射/旧入口描述已被本轮清理取代）：

# 当前建模依据与用户覆盖说明

更新日期：2026-11-06。历史整合稿保留，当前优先使用下述新版及用户覆盖。

## 2026-11-06 新版与 S1-E 覆盖

用户最新 S1-E 任务优先：只做必要实体补充和 S1 审计，不实现网络、移动、迁移。
新版仍有历史 H/L、抢占及 R2A 内部模型选择器文字；这些全部排除，不能恢复。
固定模型由配置入场绑定；未来输出/Turn/移动计划不得进入在线观察。

两份用户桌面 ZIP 的 Markdown 按原字节保留，未修改论文：

- `2026-11-06-final/`：最终小问题修订与全量复核包。
- `2026-11-06-reachability/`：网络可达性补充包；其主文比前者只进一步补充
  移动后允许 Access/原权威 Execution 组合的双向路径预检，当前采用此更完整主文。

新版 B.3/C.1 明确独立秒级移动检查、邻接 Markov、Turn 内合法 Handover、
原 Token 来源/路径保留、计划与实际 Access 分离、零 Idle。
S1-E 只提供静态 Area 归属、初始/提交 Access 快照、冻结输出 Token 身份与真实生成归属；
S2 再接入 Area 注册表/有向网络及可达性验证，S3 再实现独立私有移动过程与受控切换。
不能用直接修改位置字段代替 Handover，不能把旧 per-Turn Access 配置当作新版移动。

正式 TurnPlan 只含 input_tokens/hidden_output_tokens；旧 JSON Access 值私有隔离，
在对应 Turn 揭示时验证固定接入，否则明确拒绝。不会提前暴露未来 Access。
S1-E 完整审计见 `../S1-E_最终建模一致性审计报告.md`，原报告保留为阶段历史。

## 采用顺序

1. 用户最新 Foundation 任务及本目录 `开发建模注意.md` 为执行规范：**删除 Session 优先级及 GPU 抢占；隔离未来负载；按事件检查真实 Token**。规范由桌面 `说明文档/开发建模注意.md` 按原字节复制；其中服务器上传建议不构成本地代理的执行授权。
2. 当前主文为上述 `2026-11-06-reachability/` 修订版。本目录
   `Stateful_AI_Session_Re-placement_Section_III_完整中文系统建模.md`
   为保留的历史整合稿，来自用户提供的
   `C:/Users/71968/Desktop/Section_III_完整整合与核查_2026-11-03.zip`。
3. 同包的公式依据核对表和最终一致性检查报告作为辅助资料，不视为代码已经实现或测试通过的证明。
4. 用户提供的 `C:/Users/71968/Desktop/建模文档.zip` 为旧版分节参考；
   与完整整合稿冲突时，以完整整合稿及用户最新要求为准。

三个源 Markdown 按 ZIP 内原始字节复制，未修改论文正文。原文中的 H/L 属性、
C.4 抢占与恢复、式(20)、高低优先级队列及分组指标等相关表述不构成当前实现要求。
当前 S1-A 的事件 priority 数值用于同刻事件排序，不表示 Session 优先级。
Foundation 已删除 S0 历史 H/L 字段及合法值检查；旧配置含该字段时明确拒绝迁移，不能重新启用服务优先级。

## 当前实现与模型的对应

- S0：单 Session 的输入上传、逐 Token Prefill/Decode、累计 Context/KV、流式下行、完整 Turn E2E 和自然结束释放。
- S1-A：对应 C.3 的动态等权共享和累计服务守恒（主要是式(17)–(18)），支持通用 eq-work 任务。
- Foundation：结构派生 ModelSpec、固定绑定 SessionState、已揭示 TurnState、EdgeState、GPUComputeTask、私有 WorkloadPlan/Driver、白名单 OnlineObservation。S0 已改用这些实体和原 GPUQueue。
- S1-C0 已整理为 core/resources/simulation/demos 子包，原路径为轻量兼容入口；RuntimeState 在 core/runtime.py，实体定义仍唯一。
- S1-C1 的 KVResource 统一原子 Token/Context/KV 提交、保留 PendingCommit、阻塞计时、自然释放及确定性释放事件重试。使用原 GPU 已完成单元，不取消或重算。GPU 完成不等于合法 Token 提交或完整 Turn 交付。
- S1-B：已实现独立 L_e 运行名额、按实际 Ready 时间和稳定提交顺序的 FCFS 队列、Ready/Start/Completion 时间与等待时间；复用 S1-A 工作量和事件预测。
- S1-D 已实现统一多 Session、多 Turn、无线上传/流式下行、KV 恢复与完整 E2E。最高约束：运行名额按 Turn 计，连续 Token 保留同一 GPUQueue 资格；结束计算或 KVBlocked 才释放。底层原子任务模式仅保留给历史组件接口。
- 尚未实现有线 Max-Min、移动、迁移与策略；S1-D 固定 Access=Execution，S1-E 已补充实体语义并完成本地总体验收。S1-C 原演示保留为历史脚本化资源验收，正式统一执行位于 simulation/serving.py。
- S1-B 依据用户最新开发任务仅实现名额和 FCFS；不因原稿保留优先级规则而扩展任务范围。净显存约束明确留到 S1-C。
- GPU 运行名额释放不等于 Session KV 释放；后者须遵循模型生命周期。

模型核查报告保留的边界同样保留：未全部完成时不伪造全量平均 E2E；
切换前后同 Turn 响应在新版中按 FIFO 串行批段取得唯一活动有线公平份额，需在 S2/S3 实现。
当前阶段不自行补充算法或更改建模。

## 完整性记录（SHA-256）

```text
09703aa449639012986b92a8a57cdd7472af770f9b8daadfc281f93a9afa8440  Stateful_AI_Session_Re-placement_Section_III_完整中文系统建模.md
cd438e6cb7f866bd3d027a5dc7601880c18b17f50323448610d9af0b37f01916  Section_III_公式与参考文献依据核对表.md
11af5cf4e9077c65f2464e3ccb305c030d2f220274c94be4306aa606e381c91d  Section_III_最终一致性检查报告.md
```
