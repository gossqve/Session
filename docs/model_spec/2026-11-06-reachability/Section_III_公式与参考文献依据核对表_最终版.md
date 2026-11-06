# Section III 公式与参考文献依据核对表（最终版）

核查日期：2026-11-06。直接依据11月5日整合稿及本次F01–F08要求修订；未回退修改分散A/B/C1/C2/D稿。原21条References编号、条目及历史链接保持；本轮只复核引用与模型的对应范围，未声称重新在线阅读所有文献。

依据类型：[A]原文直接支持机制；[B]相关背景；[C]数学定义、张量维度或守恒推导；[D]本文仿真假设。组合类型不表示文献直接给出本文精确公式；正文中的“本文采用”“定义”“推导”用于区分这些性质。下表引用统一为正文编号。

## 一、全部编号公式

| 公式/机制 | 所在章节 | 对应源文档 | 参考文献及链接 | 依据类型 | 核查结果 |
|---|---|---|---|---|---|
| (1) 无线有效速率 | B | B | [4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (2) 有向链路容量 | B | B | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (3) 渐进填充残余容量与步长 | B | B | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | A/C/D | 原文支持主要机制；本文符号、参数及组合另作定义 |
| (4) 网络字节供给及速率换算 | B | B | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (5) 固定时间移动检查机会 | B | 本次Mobility修订 | [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | B/D | 间隔为秒、起点为实际到达；文献支持时间离散化，按会话设置独立时钟为本文假设 |
| (5a) Access转移概率及合法邻接 | B | 本次Mobility修订 | [2]作者机构全文，见下方新增核验 | B/C/D | 非负、行和为1；只保持或移到合法邻接；具体矩阵与有线拓扑独立配置 |
| (5b) 独立移动计划及分段常值计划Access | B、C | 本次Mobility修订 | 本文定义；[2]仅提供背景 | C/D | 第0项定义初始Access，第n项是第n次检查后的位置；按共同Seed/Session ID/序号的稳定随机流顺序按需生成，未来不可见 |
| (5c) 实际切换时刻与延期 | B、E | 本次Mobility修订 | 本文定义 | C/D | 仅对实际执行的有效移动定义；实际接入生效与旧数据排空结束区分 |
| (5d) 排空结束及持续时间 | B、E | 本次F07 | 本文事件统计定义 | C/D | 最后一个冻结旧Token完整到UE；空集合为0；未完成仅观察时长，不虚构结束 |
| (6) 固定模型和优先级 | C | C1 | 无外部引文；依定义/守恒或本文规则 | D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (7) 分离的多轮负载与移动计划 | C | 完整稿C及本次修订 | [5](https://doi.org/10.1145/3689031.3696086)；[6](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (8) 零轮间等待 | C | C1 | [5](https://doi.org/10.1145/3689031.3696086) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (9) 累计Context及单轮输出限制 | C | C1 | [18](https://docs.vllm.ai/en/latest/api/vllm/config/model/)；[19](https://docs.vllm.ai/en/stable/api/vllm/sampling_params/) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (10) 本轮输入合法性与实际输出上界 | C | C1 | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (11) 计划合法负载充分条件 | C、E | C1/E | [5](https://doi.org/10.1145/3689031.3696086) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (12) KV张量结构与每Token字节 | C | C1/C2 | [7](https://arxiv.org/abs/2309.06180)；[8](https://aclanthology.org/2023.emnlp-main.298/)；[17](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (13) Token提交与KV增长 | C | C1/C2 | [7](https://arxiv.org/abs/2309.06180)；[17](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (14) 普通文本数据量 | C、B | C1/B | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (15) 已提交工作量与部分服务守恒 | C | C2 | [9](https://www.usenix.org/conference/osdi22/presentation/yu)；[10](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (16) GPU运行集合及双容量约束 | C | C2 | [20](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (17) 动态等权GPU共享 | C | C2 | [11](https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html)；[12](https://www.usenix.org/conference/osdi18/presentation/xiao)；[13](https://developer.nvidia.com/blog/memory-enforced-gpu-sharing-in-kubernetes-with-nvidia-cuda-13-4/)；[14](https://docs.nvidia.com/run-ai/self-hosted/v3.0/documentation/platform-management/runai-scheduler/resource-optimization/gpu-fractions/compute-modes) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (18) GPU服务积分守恒 | C | C2 | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (19) 累计GPU等待与状态时间 | C | C2 | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (20) 抢占受害者与一换一转换 | C | C2 | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[15](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (21) 净KV容量与权威占用 | C | C2 | [7](https://arxiv.org/abs/2309.06180)；[21](https://docs.vllm.ai/en/latest/api/vllm/config/cache/) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (22) 完整响应事件与Turn端到端时延 | B、C、E | B/C1/E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (23) 一次性SLA预警时刻 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (23a) 实际Access变化触发申请 | B、D | 本次Mobility修订 | 本文定义 | C/D | 计划到期不提前触发；实际Access原子变化才申请，排空结束不重复申请 |
| (24) 唯一目标及实际节点模型兼容 | D、E | D/E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (25) Shadow包含关系与在途容量 | D、C、E | D/C2/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[7](https://arxiv.org/abs/2309.06180)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (26) 启动时完整已有KV容量承诺 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (27) 初始快照与增量尾部守恒 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | A/C/D | 原文支持主要机制；本文符号、参数及组合另作定义 |
| (28) 实际复制速率和尾部变化趋势 | B、D | B/D | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (29) 普通迁移STOP必要准入 | D、E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (30) 冻结状态和固定尾部 | D | D | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (31) 成功Cutover和真实冻结时间 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | A/C/D | 原文支持主要机制；本文符号、参数及组合另作定义 |
| (32) 失败回源中断与累计STOP上限 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (33) 因果联合布局接口 | D、E | D/E | [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (34) 全量计划合法Turn分母 | C、E | C1/E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (35) 全量平均完整Turn时延 | E | E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (36) KV迁移字节与物化Shadow时间 | D、E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (37) 每计划Turn归一化迁移开销 | E | E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (37a) 实际普通Handover转发Byte | B、E | 本次Mobility修订 | 本文定义及式(4)守恒 | C/D | 阶段f独立记G/Y，新转发阶段Y从0开始；与KV/正常下行/输入交接分账，截尾只记实际Byte，不加入目标 |
| (38) 共同评价集上的完整交付策略子集目标 | E | 本次F01及原E评价规则 | 本文评价定义，不外引文献 | C/D | 最小化域改为因果/安全/完整交付子集；共同评价集预先固定，期望须可计算；非运行期强制完成 |
| (39) 完成度与未完成分解 | E | E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (40) 真实SLA违约与分组统计 | D、E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (41) 唯一权威GPU计算资格 | C、D、E | C2/D/E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |

## 二、非公式关键机制

| 公式/机制 | 所在章节 | 对应源文档 | 参考文献及链接 | 依据类型 | 核查结果 |
|---|---|---|---|---|---|
| 三域直连、全双工固定路径、逻辑边界只转发 | A/B | A/B | 本文规则，无强行外引 | D | 本文拓扑假设；未宣称外部文献逐字验证 |
| 独立有效无线、不模拟RTT/控制字节/逐跳缓存 | B | B | [4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | B/D | 对数无线速率有据；排除项是本文简化 |
| 单Turn单活动下行流及串行接续 | B | 完整稿B及本次修订 | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | B/D | Max-Min依据保留；FIFO路径批段及第一层旧有线整批屏障保留；额外有线转发与新Access无线按完整Token流水，不使用多分支合流求解器 |
| Token完整到Access后无线发送、FIFO及Decode流水 | B/C | B/C1 | [9](https://www.usenix.org/conference/osdi22/presentation/yu)；[10](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | B/D | 迭代和仿真有背景；两级交付接口为本文规则 |
| 固定绑定、零Idle、未来不可见、独立时间移动 | B/C | 完整稿及本次修订 | [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process)；[5](https://doi.org/10.1145/3689031.3696086) | B/D | 时间离散移动有背景；零Idle、外生计划确定性按需生成及保护接续是本文规则 |
| 统一累计等待排序、同刻更新、同级不抢占 | C | C2 | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[15](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang)；[20](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | B/D | 源稿局部FCFS表述按详细累计等待排序统一 |
| KVBlocked保存满阈值部分服务、不提交、不重复计算 | C | C2 | [7](https://arxiv.org/abs/2309.06180) | B/C/D | 有限KV背景；恢复与阻塞执行是本文定义 |
| 四类Check、冷却待办、容量安全绕过 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/D | 未把本文触发和合并机制说成Llumnix原算法 |
| 初始/增量在线复制、末段冻结、目标预分配 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | A/D | 核对Llumnix §4.2及Fig.6–7、Clark阶段机制 |
| 排队输入真实交接、Prefill完成、Decode完整Token边界 | C/D | B/C2/D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/D | 本文安全接口；无免费输入传输或Kernel迁移 |
| STOP跨Turn仍提交，但实际上传延期 | C/D | B/C1/C2/D | 本文规则，无强行外引 | D | 不改提交时间，不向旧源制造新在途输入 |
| 复用/延后/取消、唯一ID、失败历史成本保留 | D/E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 同会话禁止冲突Copy；历史集与活动集分开 |
| 全量合法Turn分母、未完成不可伪造完整均值 | E | C1/E | 本文规则，无强行外引 | C/D | 目标仅在指标有定义的评价范围适用，非所有安全策略完整排序 |
| SLA预警保留但非硬约束；成本统计非成本优化保证 | D/E | D/E | 本文规则，无强行外引 | D | 按用户六项确认，不另加权重、预算、罚分 |

## 三、正文文献核查记录与引用范围

下表沿用输入稿的历史核验记录：[2][3]核验日期为2026-11-05，其余为此前输入记录；本轮未重新打开这些URL。相应正文条目及文献支持范围未改变。

| 编号 | 在线状态与核查材料 | 准确支持范围 |
|---|---|---|
| [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | 已在线读取上述一手材料；官方会议页与PDF §4.2、Fig.6–7；KV追加式在线复制、预分配、清理；不保证本模型跨域性能 | 仅限所列机制；未逐字移植公式 |
| [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | 2026-11-05已重新读取IBM作者机构页及作者机构公开全文；全文§III和§V支持邻接随机移动，§VI-A说明固定物理时长的离散时隙；不支持本文Prompt/Token保护和串行排空规则 | 仅限所列机制；未逐字移植公式 |
| [3](https://www.rfc-editor.org/rfc/rfc5166.html) | 2026-11-05已重新读取RFC §2.3.2，确认从零等幅增加、路径饱和即冻结的Progressive Filling；Informational，不证明本文Handover串行规则 | 仅限所列机制；未逐字移植公式 |
| [4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | 已在线读取上述一手材料；PMC期刊全文核对作者、2020年及通信模型；无线折减系数和独立分配为本文简化 | 仅限所列机制；未逐字移植公式 |
| [5](https://doi.org/10.1145/3689031.3696086) | 已在线读取上述一手材料；arXiv作者全文及EuroSys 2025官方录用列表核对；DOI直达403，非以403否认正式发表；多轮KV复用，包含Think Time | 仅限所列机制；未逐字移植公式 |
| [6](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost) | 已在线读取上述一手材料；USENIX页核对作者、ATC 2024及页码；只引用多轮复用，不移植分层缓存 | 仅限所列机制；未逐字移植公式 |
| [7](https://arxiv.org/abs/2309.06180) | 已在线读取上述一手材料；作者arXiv页核对标题/作者及SOSP 2023注记；ACM DOI直达403；动态KV与容量背景，字节式为推导 | 仅限所列机制；未逐字移植公式 |
| [8](https://aclanthology.org/2023.emnlp-main.298/) | 已在线读取上述一手材料；ACL正式页面核对EMNLP 2023、作者、DOI、页码；KV heads区别 | 仅限所列机制；未逐字移植公式 |
| [9](https://www.usenix.org/conference/osdi22/presentation/yu) | 已在线读取上述一手材料；USENIX页核对OSDI 2022、作者、页码；迭代生成，本文不采用其Batch算法 | 仅限所列机制；未逐字移植公式 |
| [10](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | 已在线读取上述一手材料；MLSys正式页面核对作者/2024；基于Profiling仿真，本文不继承其误差结论 | 仅限所列机制；未逐字移植公式 |
| [11](https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html) | 已在线读取上述一手材料；MLSys正式题名没有Salus前缀，已修正；GPU切换与共享背景，不证明精确Turn级1/n | 仅限所列机制；未逐字移植公式 |
| [12](https://www.usenix.org/conference/osdi18/presentation/xiao) | 已在线读取上述一手材料；USENIX页核对OSDI 2018作者/页码；训练调度背景，不当作LLM推理原式 | 仅限所列机制；未逐字移植公式 |
| [13](https://developer.nvidia.com/blog/memory-enforced-gpu-sharing-in-kubernetes-with-nvidia-cuda-13-4/) | 已在线读取上述一手材料；NVIDIA页核对2026-10-27、三位作者及计算模式；工作负载/容器层共享，不是硬件精确Turn执行 | 仅限所列机制；未逐字移植公式 |
| [14](https://docs.nvidia.com/run-ai/self-hosted/v3.0/documentation/platform-management/runai-scheduler/resource-optimization/gpu-fractions/compute-modes) | 已在线读取上述一手材料；Run:ai v3.0官方页核对活跃任务近似等份与空闲回收；不宣称本项目已部署该产品 | 仅限所列机制；未逐字移植公式 |
| [15](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang) | 已在线读取上述一手材料；USENIX NSDI 2026正式页核对作者、年份/页码；Token抢占背景，本文排序及原地KV保留自定 | 仅限所列机制；未逐字移植公式 |
| [16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | 已在线读取上述一手材料；USENIX原文核对八位作者、2005及Reservation/Pre-copy/Commit；VM脏页不同于追加KV | 仅限所列机制；未逐字移植公式 |
| [17](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation) | 已在线读取上述一手材料；HF固定v4.57.0文档核对KV形状和增长；同构全上下文是本文适用范围 | 仅限所列机制；未逐字移植公式 |
| [18](https://docs.vllm.ai/en/latest/api/vllm/config/model/) | 已在线读取上述一手材料；vLLM官方Model配置页面核对max_model_len；最新页面不是实验锁定版本 | 仅限所列机制；未逐字移植公式 |
| [19](https://docs.vllm.ai/en/stable/api/vllm/sampling_params/) | 已在线读取上述一手材料；vLLM官方Sampling页面核对max_tokens；用于上限语义，不模拟完整框架 | 仅限所列机制；未逐字移植公式 |
| [20](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | 已在线读取上述一手材料；vLLM官方Scheduler页面核对运行数等配置；不能代替本文eq-work/s校准 | 仅限所列机制；未逐字移植公式 |
| [21](https://docs.vllm.ai/en/latest/api/vllm/config/cache/) | 已在线读取上述一手材料；vLLM官方Cache页面核对缓存配置；净容量拆账是本文定义 | 仅限所列机制；未逐字移植公式 |

## 四、输入来源链接全量清单及去向

以下为2026-11-03输入核对表保留的六份历史来源链接清单，未回退重读或拼接这些分散稿；同文不同URL仍列出用于追溯。未纳入正文的重复、背景或实验配置候选不作为正文已核验依据，不等于认定其错误。没有取得内容的候选统一标为“未在线核验”，不推断发表状态。

| 原始链接 | 出现于源稿 | 正文去向/核验状态 |
|---|---|---|
| [链接](https://aclanthology.org/2023.emnlp-main.298/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[8]；核验范围见上表 |
| [链接](https://arxiv.org/abs/1506.05261) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/abs/1706.03762) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/abs/1809.05239) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/abs/2309.06180) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[7]；核验范围见上表 |
| [链接](https://arxiv.org/abs/2405.05465) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/abs/2603.28018) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/abs/2608.10545) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/html/2312.05516) | Stateful_AI_Session_Re-placement_Session_Model.md | [5]已在线核验作者全文 |
| [链接](https://arxiv.org/html/2406.03243) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/html/2603.28018) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://arxiv.org/html/2608.10545) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://conferences.sigcomm.org/sigcomm/2013/papers/sigcomm/p15.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://datatracker.ietf.org/doc/html/rfc5166) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://developer.nvidia.com/blog/memory-enforced-gpu-sharing-in-kubernetes-with-nvidia-cuda-13-4/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[13]；核验范围见上表 |
| [链接](https://docs.nvidia.com/knowledge-base/latest/vgpu-features.html) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://docs.nvidia.com/run-ai/self-hosted/v3.0/documentation/platform-management/runai-scheduler/resource-optimization/gpu-fractions/compute-modes) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[14]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/latest/api/vllm/config/cache/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[21]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/latest/api/vllm/config/model/) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[18]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[20]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/stable/api/vllm/sampling_params/) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[19]；核验范围见上表 |
| [链接](https://doi.org/10.1002/spe.2755) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://doi.org/10.1016/j.future.2016.05.003) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://doi.org/10.1109/TNET.2002.1012364) | Stateful AI Session Re-placement：Network Model.md | DOI工具无法访问；正文改引已核验RFC，未在线核验该论文全文 |
| [链接](https://doi.org/10.1109/TWC.2023.3290005) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://doi.org/10.1145/2486001.2486012) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://doi.org/10.1145/3600006.3613165) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | [7]DOI直达403，改用作者公开版本交叉核验 |
| [链接](https://doi.org/10.1145/3689031.3696086) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[5]；核验范围见上表 |
| [链接](https://github.com/vllm-project/vllm/blob/main/benchmarks/multi_turn/README.md) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://huggingface.co/Qwen/Qwen3-4B/blob/main/config.json) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[17]；核验范围见上表 |
| [链接](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/config.json) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://ieeexplore.ieee.org/document/10173745/) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://onlinelibrary.wiley.com/doi/full/10.1002/spe.2755) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | Stateful AI Session Re-placement：Network Model.md | 正文[4]；核验范围见上表 |
| [链接](https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[11]；核验范围见上表 |
| [链接](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[10]；核验范围见上表 |
| [链接](https://proceedings.nips.cc/paper_files/paper/2024/hash/724be4472168f31ba1c9ac630f15dec8-Abstract-Conference.html) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[2]；核验范围见上表 |
| [链接](https://shiqiang.wang/papers/WS_Networking2015.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://team.inria.fr/rap/files/2013/12/MR02.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.lk.cs.ucla.edu/data/files/Kleinrock/Processor%20Sharing%20Queueing%20Models%20of%20Mixed.pdf) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.nature.com/articles/s41598-026-36711-y) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.nvidia.cn/geforce/graphics-cards/compare/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.rfc-editor.org/rfc/rfc5166.html) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[3]；核验范围见上表 |
| [链接](https://www.sciencedirect.com/science/article/pii/S0167739X16301133) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[6]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[15]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi22/presentation/yu) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[9]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/agrawal) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[1]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/zhong-yinmin) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；本次未在线核验，保留历史追溯 |
| [链接](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[16]；核验范围见上表 |
| [链接](https://www.usenix.org/system/files/osdi24-sun-biao.pdf) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | [1]已在线核验全文 |

## 五、有效机制的依据边界

| 规则 | 类型 | 本次核验及适用边界 |
|---|---|---|
| 固定物理时间间隔、保持/相邻Access随机转移 | B/D | [2]全文§V和§VI-A提供相关背景；本文采用每会话到达为起点及通用矩阵，不复制其具体距离MDP或转移数值 |
| 所有算法复用相同外生计划、实际Access可因保护滞后 | C/D | 公平实验定义；不宣称实际切换时刻也与策略完全无关 |
| Prompt开始上传至完整到Execution期间保护 | D | 本文仿真简化；未引用为3GPP或文献[2]原始机制 |
| 当前无线Token完成后切换、已交付Token不重发 | C/D | 本文数据接续边界；与Token生成/KV提交边界分离 |
| 旧输出冻结、原有线完成、转发/无线流水、新输出解缓冲 | C/D | 旧原有线整批屏障保留，后续转发与无线可流水；单Turn最多一个活动有线流，不模拟逐跳缓存，实际Byte遵守式(2)–(4) |
| Execution Cutover后的不同来源响应按FIFO路径批段串行 | D | 为满足单Turn单活动流及既有FIFO所作的必要接口明确；Max-Min算法不变 |
| 不重叠Handover、FIFO待办、每时间戳至多一次实际切换 | D | 本文轻量保护；未引入移动规划器或额外优化目标 |
| 剩余待办在严格更晚的下一移动检查/服务事件重验 | D | 实现“不在同刻批量切换”的最小事件约定；不人为设时间步长或改变外生计划 |
| MoveCheck在实际Access更新时申请，旧数据排空不重复触发 | C/D | 与D原冷却、合并规则配合；接入生效时刻与排空结束区分 |
| Handover与KV Copy/STOP/Cutover独立 | C/D | KV核心公式未变；Handover不许可STOP输入越界或双权威 |
| 普通转发Byte、延期及未执行待办统计 | C/D | 辅助指标，不是KV成本或主目标；未执行不虚构完成时刻 |

输入稿于2026-11-05核验的[2]全文：[作者机构公开稿](https://bpb-us-e1.wpmucdn.com/sites.psu.edu/dist/a/74125/files/2019/05/Shiqiang19TON.final_.pdf)。论文标题、作者和正式发表信息同时由[IBM机构页](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process)交叉核对。保持原参考文献[2]链接和编号，未新增未经核验的文献条目。未使用3GPP规范作直接依据，因为正文规则是仿真简化，不声明实现真实无线协议。

## 六、F01–F08依据与检查边界

| 项目 | 依据类型 | 当前解释 |
|---|---|---|
| F01 完成交付评价域 | C/D | 数学定义域修复，不是文献提出的新运行期机制；不对未完成运行补罚分或筛掉困难负载。 |
| F02 转发/无线流水 | C/D | 删除第二重整批无线等待，保留第一层和单有线公平份额；无线独立。 |
| F03 按需随机计划 | D | 共同Seed/Session ID/检查序号固定随机流，按上一计划位置的矩阵行顺序采样；实现可复现外生过程，不新增策略动作。 |
| F04 配置合法性 | C/D | 初始化排查非零转移及正常业务所需有向路径；错误配置不进入算法评价。 |
| F05 分阶段Byte | C/D | 同一Token跨阶段保持全局ID，新阶段G/Y独立；后段Y不能继承前段完成量。 |
| F06 同刻顺序 | D | 既有D安全条件优先，七步事件处理统一B/D；新启动传输在推进前重验绑定。 |
| F07 排空统计 | C/D | 真实交付事件定义，未完成删失；辅助指标不加入优化目标。 |
| F08 轻量保护 | D | FIFO待办及同刻一次保留，仅记录诊断，不新增规划/丢弃/放宽容量。 |

## 七、A–E完整符号使用与量纲表

表中逗号并列者为同一物理量的索引别名或省略时间/实例参数写法，已明确其对应关系；不同下标或修饰形成不同完整符号，不按字母外观误判。首次定义位置包括定义式及紧邻解释，表Ⅰ概览与正文展开共同构成定义。索引、算子也列出以明确集合元素类型。

| 完整LaTeX符号 | 首次定义位置 | 物理/数学含义 | 单位或类型 | 所属章节 | 后续使用位置 |
|---|---|---|---|---|---|
| $\mathcal R$ | A首段 | 服务区域集合 | 集合（区域） | A、B | B §1、表Ⅰ |
| $\mathcal E_r$ | A首段 | 区域r内Edge集合 | 集合（Edge） | A | 表Ⅰ |
| $\mathcal E$ | A首段 | 全部Edge集合 | 集合（Edge） | A–E | 式(2)(5a)(24)(25)(41) |
| $\mathcal M$ | A首段 | 候选LLM集合 | 集合（模型） | A | 表Ⅰ；不作迁移集合 |
| $r,r'$ | A首段、B §1 | 区域索引 | 区域 | A、B | B §1跨域路径 |
| $e,e'$ | A首段 | Edge及候选Edge索引 | Edge | A–E | 式(2)(5a)(16)(24)(25)(41) |
| $\rho(e)$ | 表Ⅰ、B §1 | Edge所属区域 | 区域 | A、B | B §1 |
| $x_{e,m}$ | A首段 | 固定模型预部署标记 | 0或1 | A、D、E | 式(24) |
| $m$ | A首段及式(12)参数说明 | 模型索引 | 模型 | A、C、D | 式(12)(15)(24) |
| $g_r$ | B §1 | 区域逻辑转发边界，无模型服务 | 逻辑节点 | B | B §1跨域路径 |
| $\mathcal S(t)$ | 表Ⅰ、C §1 | 未终止会话集合 | 集合（Session） | A、C、D | 式(21)(24) |
| $s$ | A首段及表Ⅰ | 稳定会话索引 | Session ID | A–E | 所有会话状态和移动随机流 |
| $q=(s,k)$ | 表Ⅰ、C §1 | 会话s第k轮请求 | Turn索引 | A–E | 式(14)–(23)(33)–(41) |
| $k$ | 表Ⅰ、C §1 | 会话轮次序号 | 正整数索引 | A–E | 式(7)–(11)(22) |
| $J_s$ | 表Ⅰ、C §1 | 计划总轮数 | Turn数 | A、C、E | 式(7)–(11)，策略不可预读 |
| $m_s,m_s(t)$ | 表Ⅰ、C §1 | 会话固定绑定模型及其时间写法 | 模型 | A–E | 式(6)(9)(12)(24) |
| $p_s,p_s(t)$ | 表Ⅰ、C §1 | 固定优先级及其时间写法 | H或L | A、C、E | 式(6)(20)(40) |
| $q_s^{\mathrm{initial}}$ | C §1式(6)前 | 模型选择使用的初始请求 | 请求对象 | C | 式(6) |
| $\operatorname{R2A}$ | C §1式(6)前 | 已有模型选择器，不是运行期动作 | 映射 | C | 式(6) |
| $a_s(t)$ | 表Ⅰ、B §3 | 实际生效Access | Edge | A–E | 式(23a)、B/D接续、E观测 |
| $y_s(t)$ | 表Ⅰ、A首段 | 唯一权威Execution | Edge | A–E | 式(18)(21)(24)(31)(41) |
| $z_{s,e,j}$ | 表Ⅰ、D §1 | 第j次检查的目标Edge二元指派 | 0或1 | A、D、E | 式(24)(33) |
| $\boldsymbol z_j$ | E §1式(33) | 所有存活会话的目标布局 | 二元向量 | E | 式(33) |
| $j,t_j$ | D §1首段 | 联合检查序号和发生时刻 | 索引；s | D、E | 式(24)(33)，不作传输索引 |
| $\mathcal L$ | 表Ⅰ、B §1 | 有向有线连接集合 | 集合（有向连接） | A、B | 式(2)(3)(5a)邻接区分 |
| $\ell$ | 表Ⅰ、B §1 | 有向连接索引 | 连接 | B | 式(2)(3) |
| $B_\ell$ | 表Ⅰ、B §1 | 有向连接容量 | bit/s | A、B | 式(2)(3) |
| $f$ | B §2首段及式(4)后 | 具体有线传输阶段索引 | 任务/阶段ID | B、D、E | 式(2)–(4)(28)，跨阶段不同ID |
| $\mathcal F(t)$ | B §2首段 | 已启动且有待发字节的活动有线阶段 | 集合（f） | B | 式(2) |
| $\mathcal P_f$ | 表Ⅰ、B §2 | 传输阶段固定有线路径 | 有向连接路径 | A、B | 式(2)(3) |
| $r_f(t),r_f$ | 表Ⅰ、B §2 | 端到端有线速率；省略时间为分配迭代内值 | bit/s | A、B、D | 式(2)–(4)(28) |
| $\mathcal U$ | B §2式(3)前 | 本次渐进填充尚未冻结的阶段集合 | 集合（f） | B | 式(3) |
| $C_\ell^{\mathrm{res}}$ | B §2式(3) | 分配迭代中的剩余连接容量 | bit/s | B | 式(3)，不是显存容量 |
| $\nu_\ell$ | B §2式(3) | 经过连接的未冻结阶段数量 | 无量纲计数 | B | 式(3) |
| $\delta$ | B §2式(3) | 本次公平填充的共同速率增量 | bit/s | B | 式(3)，不同于时间冷却或移动延期 |
| $G_f(t),G_f$ | B §2式(4)前 | 本阶段累计就绪Byte | Byte | B、E | 式(4)、额外转发独立初始化 |
| $Y_f(t),Y_f$ | B §2式(4)前 | 本阶段累计交付Byte | Byte | B、E | 式(4)(37a)解释 |
| $V$ | B §2式(4)后 | 单次示意数据量 | Byte | B | 8V/r及阶段重置说明 |
| $d$ | B §1式(1)前 | 无线方向 | up或down | B | 式(1) |
| $W_s^d(t),W_s^d$ | 表Ⅰ、B §1 | 用户有效无线带宽 | Hz | A、B | 式(1)，不是GPU工作量 |
| $\gamma_s^d(t),\gamma_s^d$ | 表Ⅰ、B §1 | 线性信噪比 | 无量纲 | A、B | 式(1) |
| $\eta_s^d(t),\eta_s^d$ | 表Ⅰ、B §1 | 无线实现折减系数 | 无量纲，(0,1] | A、B | 式(1) |
| $R_s^d(t),R_s^d$ | 表Ⅰ、B §1 | 独立无线有效速率 | bit/s | A、B | 式(1)(4)后无线推进 |
| $b^{\mathrm{text}}$ | 表Ⅰ、B §3 | 普通文本每Token换算字节 | Byte/token | A–E | 式(14)、D §3输入交接 |
| $h$ | B §3首段 | 同一Turn输出Token序号 | 正整数索引 | B、C | 式(22) |
| $t_{q,h}^{\mathrm{gen}}$ | B §3首段 | 输出Token合法生成/提交时刻 | s | B、C | 式(22) |
| $t_{q,h}^{\mathrm{recv}}$ | C §5式(22) | 输出Token完整送达UE时刻 | s | B、C、E | 式(22)、排空结束说明 |
| $t_s^{\mathrm{arr}}$ | B §3固定时间移动 | 会话实际到达时刻 | s | B、C、E | 式(5)(5b) |
| $a_s^{\mathrm{init}}$ | B §3固定时间移动 | 会话初始Access | Edge | B、C、E | 式(5b)第0项、工作负载 |
| $a_{s,0}^{\mathrm{plan}}$ | B §3固定时间移动 | 初始计划Access，等于初始Access | Edge | B | 式(5a)(5b)起点 |
| $a_{s,n}^{\mathrm{plan}}$ | B §3式(5a)附近 | 第n次移动检查后的计划Access | Edge | B、C、E | 式(5a)(5b)(7)，n非Turn序号 |
| $n$ | B §3式(5) | 移动检查序号，n=0仅为初始项 | 整数索引 | B、C、E | 式(5)–(5d)(7) |
| $\Delta_{\mathrm{mob}}$ | 表Ⅰ、B §3 | 固定移动检查时间间隔 | s，正数 | A、B | 式(5)(5b)，不是决策间隔 |
| $t_{s,n}^{\mathrm{mob}}$ | 表Ⅰ、B §3 | 第n次外生移动检查时刻 | s | A–E | 式(5)(5b)(5c)(7) |
| $P_{e,e'}$ | 表Ⅰ、B §3式(5a) | 计划位置Markov转移概率 | 无量纲，0到1 | A、B | 初始化检查、随机流按需生成 |
| $\mathcal N^{\mathrm{mob}}(e)$ | 表Ⅰ、B §1 | 合法移动邻接Access集合 | 集合（Edge） | A、B | 式(5a)，独立于有线拓扑 |
| $\mathcal H_s$ | 表Ⅰ、B §3式(5b) | 数学上的外生移动计划 | 事件序列 | A–E | 式(7)、按需随机流、E外生实例 |
| $a_s^{\mathrm{plan}}(t)$ | 表Ⅰ、B §3式(5b) | 时刻t的计划Access | Edge | A、B | 计划/实际差异及因果观测 |
| $t_{s,n}^{\mathrm{HO}}$ | 表Ⅰ、B §3式(5c) | 已执行有效移动的Access原子生效时刻 | s | A、B、E | 式(5c)(5d)，非排空结束 |
| $\delta_{s,n}^{\mathrm{HO}}$ | B §3式(5c) | 计划到期到实际接入生效的延期 | s | B、E | 辅助延期统计 |
| $t_{s,n}^{\mathrm{drain,end}}$ | B §3式(5d)前 | 冻结旧集合最后Token完整交付时刻 | s | B、E | 式(5d)，未完成不定义 |
| $T_{s,n}^{\mathrm{drain}}$ | B §3式(5d) | 已完成Handover的排空持续时间 | s | B、E | 辅助排空统计，空集合为0 |
| $e_{\mathrm{old}},e_{\mathrm{new}}$ | B §3旧输出集合 | 实际切换前、后Access | Edge | B、E | 旧输出转发与分账 |
| $\mathcal W_s$ | 表Ⅰ、C §1式(7) | 各Turn新增输入及隐藏计划输出序列 | Turn负载序列 | A、C、E | 式(7)、共同评价实例 |
| $n_{s,k}^{\mathrm{in}},n_q^{\mathrm{in}}$ | C §1式(7)及别名说明 | 本轮新增输入Token数量 | token | C、D | 式(10)(11)(14)、输入交接 |
| $\widetilde n_{s,k}^{\mathrm{out}}$ | C §1式(7) | 仿真器隐藏的计划输出长度 | token | C | 式(10)(11)，不暴露策略 |
| $n_{s,k}^{\mathrm{out}},n_q^{\mathrm{out}}$ | C §1式(7)后 | 最终实际生成输出Token数量 | token | C、E | 式(9)(10)(14)(22) |
| $n_{s,k}^{\mathrm{in,done}},n_q^{\mathrm{in,done}}$ | C §1done约定、C §2式(9)前 | 截至当前已合法提交的输入Token数 | token | C | 式(9)(15)，q与(s,k)同一对象 |
| $n_{s,k}^{\mathrm{out,done}},n_q^{\mathrm{out,done}}$ | C §1done约定、C §2式(9)前 | 截至当前已合法提交的输出Token数 | token | C | 式(9)(15)，不等于已交付数量 |
| $t_q^{\mathrm{sub}},t_{s,k}^{\mathrm{sub}}$ | C §1式(8)前 | Turn真实提交时刻，两种索引写法 | s | B–E | 式(8)(19)(22)(23) |
| $t_q^{\mathrm{recv}},t_{s,k}^{\mathrm{recv}}$ | C §1式(8)前 | Turn完整响应到UE时刻 | s | B–E | 式(8)(19)(22)，非生成结束 |
| $N_m^{\mathrm{ctx,max}}$ | 表Ⅰ、C §2 | 模型累计Context上限 | token | A、C | 式(9)–(11) |
| $N_{\max}^{\mathrm{out}}$ | 表Ⅰ、C §2 | 单Turn新增输出上限 | token | A、C | 式(9)–(11) |
| $N_s^{\mathrm{ctx}}(t)$ | C §2式(9) | 会话所有轮次累计合法Context | token | C、D | 式(9)(12)(13) |
| $N_{s,k}^{\mathrm{hist}}$ | C §2式(10)前 | 本轮开始前的历史KV位置数 | token | C | 式(10) |
| $M_{\mathrm{KV}}(B_{\mathrm{seq}},S,m)$ | C §2式(12) | KV张量总大小 | Byte | C | 式(12) |
| $B_{\mathrm{seq}}$ | C §2式(12) | 张量序列维度，单会话取1 | 无量纲计数 | C | 式(12)，不是带宽 |
| $S$ | C §2式(12) | 张量缓存位置数 | token位置数 | C | 式(12)，不是会话集合 |
| $L_m$ | C §2式(12) | 模型的KV缓存层数 | 无量纲计数 | C | 式(12)，不是GPU名额L_e |
| $H_{\mathrm{KV},m}$ | C §2式(12) | 真实KV头数 | 无量纲计数 | C | 式(12)，非Query头数或Shadow |
| $d_{\mathrm{head},m}$ | C §2式(12) | KV头维度 | 元素数 | C | 式(12) |
| $b_m^{\mathrm{elem}}$ | C §2式(12) | 张量每元素字节数 | Byte/元素 | C | 式(12) |
| $b_m^{\mathrm{KV}}$ | 表Ⅰ、C §2式(12) | 每Token的KV字节数 | Byte/token | A、C、D | 式(12)(13)(28) |
| $K_s(t)$ | 表Ⅰ、C §2式(12) | 唯一权威KV当前大小 | Byte | A–E | 式(13)(21)(26)–(30) |
| $\Delta N_s$ | C §2式(13)前 | 本提交事件新增有效Token数量 | token | C | 式(13) |
| $V_q^{\mathrm{up}},V_q^{\mathrm{down}}$ | C §2式(14) | 普通输入/输出文本总量 | Byte | C、B | 式(14)，不含额外HO或KV |
| $C_e^{\mathrm{GPU}}$ | 表Ⅰ、C §3 | Edge等效GPU服务预算 | eq-work/s | A、C、E | 式(16)(17) |
| $L_e$ | 表Ⅰ、C §3 | 同时获得GPU服务的Turn名额 | Turn数 | A、C、E | 式(16)(20) |
| $w_m^{\mathrm{pre}},w_m^{\mathrm{dec}}$ | 表Ⅰ、C §3 | Prefill/Decode每Token等效工作量 | eq-work/token | A、C | 式(15) |
| $W_q^{\mathrm{done}}(t)$ | C §3式(15)前后 | 已合法提交Token对应工作量 | eq-work | C | 式(15)，不是无线带宽 |
| $W_q^{\mathrm{serv}}(t)$ | C §3式(15)前后 | 累计真实GPU服务量 | eq-work | C、D | 式(15)(18) |
| $w_q^{\mathrm{partial}}(t)$ | C §3式(15) | 当前未提交Token已耗服务量 | eq-work | C、D | KVBlocked保持、STOP安全边界 |
| $u_{q,e}(t)$ | C §3式(16)前 | Turn在Edge实际获得GPU服务的标记 | 0或1 | C、E | 式(16)(17)(20)(41) |
| $c_{q,e}(t)$ | C §3式(16)前 | Turn的等效GPU服务速率 | eq-work/s | C、E | 式(16)–(18) |
| $\mathcal R_e(t)$ | C §3式(16)前 | Edge实际运行Turn集合 | 集合（Turn） | C | 式(16)(17)，不是区域集合 |
| $n_e^{\mathrm{run}}(t)$ | C §3式(16) | 实际运行Turn数量 | Turn数 | C | 式(17) |
| $t,t_1,t_2,\tau$ | B及C式(18)(19) | 事件时间、积分端点/哑变量 | s | B–E | 时间积分、事件边界 |
| $t^-,t^+$ | B §3同刻处理、C式(13) | 同刻结算前和更新后的状态侧限 | s对应的事件侧状态 | B–E | 式(13)(23a)(31) |
| $I_q^{\mathrm{queue}}(t)$ | C §4式(19)前 | 就绪但未获GPU名额指示值 | 0或1 | C | 式(19) |
| $I_q^{\mathrm{compute}}(t)$ | C §4式(19)前 | 实际获得GPU计算的指示值 | 0或1 | C | 式(19) |
| $A_q(t)$ | C §4式(19) | 累计GPU就绪等待量 | s | C、D | 式(19)(20)，非网络供给量 |
| $T_q^{\mathrm{queue}},T_q^{\mathrm{compute}}$ | C §4式(19) | 累计就绪等待/实际计算时长 | s | C | 式(19)，不机械相加为E2E |
| $q_H,q_L^*$ | C §4式(20)前 | 高优先级就绪Turn及选中受害低优先级Turn | Turn索引 | C | 式(20) |
| $\mathcal R_e^{\mathrm L}(t)$ | C §4式(20)前 | 运行中的低优先级候选Turn集合 | 集合（Turn） | C | 式(20) |
| $t_q^{\mathrm{run}}$ | C §4式(20)前 | 本次进入GPU运行集合的时刻 | s | C | 式(20) |
| $\operatorname{ID}(q)$ | C §4式(20)及排序说明 | 稳定Turn ID，破平局 | 标识 | C | 式(20) |
| $\operatorname{arg\,min}_{\mathrm{lex}}$ | C §4式(20)说明 | 字典序最小选择算子 | 算子 | C | 受害者选择；不引入权重 |
| $M_e^{\mathrm{phys}}$ | C §5式(21)前 | Edge物理GPU显存 | Byte | C | 式(21) |
| $M_e^{\mathrm{weights}}$ | C §5式(21)前 | 固定部署模型权重占用 | Byte | C | 式(21)，只扣一次 |
| $M_e^{\mathrm{runtime}}$ | C §5式(21)前 | GPU运行时预留 | Byte | C | 式(21) |
| $C_e^{\mathrm{KV}}$ | 表Ⅰ、C §5式(21) | 净KV容量 | Byte | A、C、D、E | 式(21)(25) |
| $U_e^{\mathrm{KV}}(t)$ | C §5式(21) | 本Edge所有权威KV占用 | Byte | C、D | 式(21)(25) |
| $t_q^{\mathrm{end0}}$ | C §5式(22)前后 | 合法零输出结束事件时刻 | s | C | 式(22)，非阻塞时伪完成 |
| $D_q^{\mathrm{E2E}}$ | C §5式(22) | 完整响应时刻减提交时刻 | s | C、E | 式(35)(38)(40) |
| $D^{\max}$ | 表Ⅰ、D §1 | 统一完整Turn SLA阈值 | s | A、D、E | 式(23)(40) |
| $\theta$ | 表Ⅰ、D §1 | SLA预警比例 | 无量纲，(0,1) | A、D | 式(23) |
| $t_q^{\mathrm{warn}}$ | D §1式(23)前 | 当前Turn一次性预警时刻 | s | D | 式(23) |
| $\delta_{\mathrm{cool}}$ | 表Ⅰ、D §1 | 普通联合检查冷却时间 | s | A、D | Check合并/延期 |
| $\Delta_{\mathrm{check}}$ | 表Ⅰ、D §1 | 低频周期检查间隔 | s | A、D | 周期Check，不等于移动间隔 |
| $\operatorname{MoveCheck}_s(t)$ | D §1式(23a) | 实际Access变化产生的检查申请标记 | 0或1 | D、B | 与冷却合并，不是排空结束标记 |
| $\mu$ | D §2首段 | 唯一迁移操作ID | 迁移ID | D、E | 式(25)–(32)(36) |
| $s(\mu)$ | D §2首段 | 迁移操作所属会话 | Session | D | 式(25)–(31) |
| $e_{\mathrm{src}}(\mu),e_{\mathrm{dst}}(\mu)$ | D §2首段 | 迁移固定源和目标Edge | Edge | D | 式(25)(31) |
| $t_\mu^{\mathrm{start}}$ | D §2首段 | 本迁移操作启动时刻 | s | D | 式(26)(27) |
| $\mathcal I^{\mathrm{act}}(t)$ | D §2首段 | 尚未清理的有效迁移操作集合 | 集合（迁移ID） | D | 式(25)，不作模型集合 |
| $\mathcal I^{\mathrm{hist}}$ | D §2首段 | 曾启动的全部迁移操作集合 | 集合（迁移ID） | D、E | 式(36)，取消亦保留 |
| $X_\mu(t)$ | D §2式(25)前 | 目标已一致同步的KV前缀 | Byte | D | 式(25)(27)–(31) |
| $H_\mu(t)$ | D §2式(25)前 | 目标实际物化Shadow大小 | Byte | D、E | 式(25)(36)，不是移动计划 |
| $Q_\mu(t)$ | D §2式(25)前 | 含Shadow的目标总容量承诺 | Byte | D | 式(25)(26)，不与Shadow再加一次 |
| $K_\mu^0$ | D §3式(27) | 迁移启动时初始已有KV快照大小 | Byte | D | InitialDone判定 |
| $Z_\mu(t),\Delta Z_\mu$ | D §3式(27) | 当前未同步尾部及其事件增量 | Byte | D | 式(27)–(30) |
| $\Delta K_{s(\mu)},\Delta X_\mu$ | D §3式(27) | 当前事件真实KV增长和真实同步增量 | Byte | D | 尾部增量守恒 |
| $f_\mu$ | D §3式(28)前 | 本迁移Copy对应有线传输阶段ID | f索引 | D | 式(28) |
| $v_\mu^{\mathrm{copy}}(t)$ | D §3式(28) | 实际KV复制速率 | Byte/s | D | 式(28)，由bit/s除8 |
| $g_s^{\mathrm{KV}}(t)$ | D §3式(28) | 真实提交导致的KV增长速率近似 | Byte/s | D | 式(28) |
| $r_s^{\mathrm{token}}(t)$ | D §3式(28)说明 | 真实Token提交速率的连续近似 | token/s | D | 式(28)，非计划生成速率 |
| $\widehat v_\mu^{\mathrm{copy}}(t)$ | D §3式(29)前 | STOP准入时复制速率估计 | Byte/s | D | 式(29)，不保证冻结后实际速率 |
| $\mathrm{InitialDone}_\mu(t)$ | D §3InitialDone说明 | 初始完整前缀已同步的布尔条件 | 布尔 | D | 式(29) |
| $\mathrm{SafeBoundary}_\mu(t)$ | D §3式(29)前 | 输入及计算处于合法冻结边界 | 布尔 | D | 式(29)及分阶段解释 |
| $\mathrm{CapacityOK}_\mu(t)$ | D §3式(29)前 | 模型、路径和目标承诺合法 | 布尔 | D | 式(29) |
| $I_{\max}^{\mathrm{mig}}$ | 表Ⅰ、D §3 | 普通迁移预计冻结预算 | s | A、D | 式(29)，非实际中断硬保证 |
| $t_\mu^{\mathrm{stop}}$ | D §3式(30)前 | 实际进入最终STOP的时刻 | s | D | 式(30)–(32) |
| $K_\mu^{\mathrm{stop}},Z_\mu^{\mathrm{tail}}$ | D §3式(30) | 冻结权威KV总量及固定尾部 | Byte | D | 式(30)(31) |
| $t_\mu^{\mathrm{cut}}$ | D §4式(31)前 | 成功原子Cutover时刻 | s | D | 式(31) |
| $I_\mu^{\mathrm{mig}}$ | D §4式(31)前 | 成功迁移真实冻结中断 | s | D、E | 式(31)，非GPU Queue |
| $t_\mu^{\mathrm{resume}}$ | D §4式(32)前 | 失败/取消后源端安全解冻时刻 | s | D | 式(32) |
| $I_\mu^{\mathrm{mig,fail}}$ | D §4式(32) | 失败操作的真实冻结中断 | s | D、E | 式(32) |
| $N_s^{\mathrm{stop}}$ | D §4式(32)前 | 会话普通迁移实际进入STOP累计次数 | 次 | D | 式(32)，失败亦计次 |
| $M_{\max}^{\mathrm{mig}}$ | 表Ⅰ、D §4 | 累计STOP次数上限 | 次 | A、D | 式(32)，非迁移Byte预算 |
| $\mathcal O_j$ | E §1式(33)前 | 当前及历史可观测信息 | 状态对象 | E | 式(33)，无未来计划 |
| $\pi$ | E §1式(33) | 因果布局决策策略 | 策略 | E | 式(33)(35)–(38) |
| $\Pi_{\mathrm{causal}}$ | E §1式(33) | 因果策略集合 | 集合（策略） | E | 式(33) |
| $\Pi_{\mathrm{causal,safe}}$ | E §2式(38)前 | 因果且遵守B–D安全规则的策略 | 集合（策略） | E | 完整评价子集的母集 |
| $\Omega_{\mathrm{eval}}$ | E §2式(38)前 | 预先固定的共同评价工作负载集合 | 集合（外生实例） | E | 式(38)，不可按完成结果筛选 |
| $\Pi_{\mathrm{causal,safe,full}}(\Omega_{\mathrm{eval}})$ | E §2式(38)前 | 共同评价集上全量交付且期望可计算的因果安全子集 | 集合（策略） | E | 式(38)，不是运行时强制完成 |
| $\omega$ | E §1式(34)前 | 共同外生工作负载实例，含移动随机流配置 | 外生实例 | E | 式(34)–(38) |
| $\mathcal Q^{\mathrm{all}}(\omega)$ | E §1式(34)前 | 全部计划合法Turn集合 | 集合（Turn） | E | 式(34)(35)(37a) |
| $N_{\mathrm{turn}}(\omega),N_{\mathrm{turn}}$ | E §1式(34) | 全量计划合法Turn分母，后者省略实例 | Turn数 | E | 式(35)(37)(39) |
| $\overline D^{\mathrm{E2E}}(\pi;\omega)$ | E §1式(35) | 全量完整Turn端到端时延均值 | s | E | 式(35)(38)，未完成不定义 |
| $T_{\mathrm{obs}}$ | B §3式(5d)后、E §1 | 共同评价口径的观察终点 | s | B、E | 式(36)(37a)、删失记录 |
| $V_\mu^{\mathrm{actual}}(T_{\mathrm{obs}})$ | E §1式(36)前 | 迁移操作截至观察终点真实发送的逻辑KV量 | Byte | E | 式(36)，不按跳数倍增 |
| $V^{\mathrm{mig}}(\pi;\omega)$ | E §1式(36) | 所有历史操作实际KV复制量 | Byte | E | 式(36)(37) |
| $A^{\mathrm{shadow}}(\pi;\omega)$ | E §1式(36) | 物化Shadow大小对时间积分 | Byte·s | E | 式(36)(37)，不是GPU等待 |
| $\overline V^{\mathrm{mig}}$ | E §1式(37) | 每计划Turn归一化KV复制量 | Byte/Turn | E | 辅助统计 |
| $\overline A^{\mathrm{shadow}}$ | E §1式(37) | 每计划Turn归一化Shadow积分 | Byte·s/Turn | E | 辅助统计 |
| $V_q^{\mathrm{HO}}(T_{\mathrm{obs}})$ | E §1式(37a)前 | 本Turn各HO额外普通转发阶段实际Byte之和 | Byte | E | 式(37a)，不含原阶段或KV |
| $V^{\mathrm{HO}}(\pi;\omega),V^{\mathrm{HO}}$ | 表Ⅰ、E §1式(37a) | 全部Turn普通HO额外转发量 | Byte | A、B、E | 式(37a)，非主目标 |
| $N_{\mathrm{sub}},N_{\mathrm{done}}$ | E §2式(39)前 | 真实已提交数、正常完整交付数 | Turn数 | E | 式(39) |
| $N_{\mathrm{unfinished}}$ | E §2式(39) | 全量计划中未正常完整交付的Turn数 | Turn数 | E | 式(39)，含未提交后续轮次 |
| $\rho_{\mathrm{done}}$ | E §2式(39) | 全量完成比例 | 无量纲 | E | 式(39) |
| $p$ | E §2式(40)前 | 优先级分组索引 | H或L | E | 式(40) |
| $\mathcal Q_p^{\mathrm{all}}$ | E §2式(40)前 | 优先级组的全量计划合法Turn集合 | 集合（Turn） | E | 式(40) |
| $v_q^{\mathrm{SLA}}$ | E §2式(40) | 已完整交付Turn的真实违约指示 | 0或1 | E | 式(40) |
| $\rho_p^{\mathrm{SLA}}$ | E §2式(40) | 全量已完成优先级组的违约率 | 无量纲 | E | 式(40)，未完成组不伪造比例 |
| $\mathbb E_\omega$ | E §2式(38) | 共同外生实例分布下的期望算子 | 保持被积指标单位 | E | 式(38) |

共同Seed是实验配置项（随机流标识），无需新建数学状态或优化参数；Session ID、检查序号已分别由$s$、$n$表达。Normal/Pending/Draining、KVBlocked等是执行状态名称，非新增实数变量。$\Delta$表示相应量的事件增量，$\mathbf1$为指示算子，$\Pr$为概率，$\mathrm d/\mathrm dt$为时间导数；求和/集合约束中的绑定下标按所在式定义域使用。

## 八、易混淆符号及跨章节结论

| 对照 | 核查结论 |
|---|---|
| $\mathcal R$ 与 $\mathcal R_e(t)$ | 前者元素为区域，后者元素为Turn；完整符号不同，无重名。 |
| $W_s^d$ 与 $W_q^{\mathrm{done}},W_q^{\mathrm{serv}}$ | Hz与eq-work分别对应无线带宽与GPU工作量；完整符号不同，无单位漂移。 |
| $\mathcal H_s$ 与 $H_\mu$ | 外生事件序列与Byte物化Shadow；字体/下标不同，未混用。 |
| $\mathcal M$ 与 $\mathcal I^{\mathrm{act}},\mathcal I^{\mathrm{hist}}$ | 模型与迁移ID集合区分，容量仅用活动操作、历史开销用历史操作。 |
| $t^{\mathrm{mob}},t^{\mathrm{HO}},t^{\mathrm{drain,end}}$（完整下标见上表） | 计划检查、实际接入生效、最后旧Token交付三类时刻；统一秒，延期与排空时长分开。 |
| $I_{\max}^{\mathrm{mig}},I_\mu^{\mathrm{mig}},I_\mu^{\mathrm{mig,fail}}$ | 预计准入预算与实际成功/失败中断分开；不把预计预算当硬保证。 |
| $N_s^{\mathrm{ctx}},n_q^{\mathrm{out,done}},t_{q,h}^{\mathrm{recv}}$ | 累计合法KV上下文、已生成输出、UE已交付事件分开；后者不决定KV是否已生成。 |
| $G_f,Y_f$ 与 $V^{\mathrm{HO}},V^{\mathrm{mig}}$ | 前者是具体阶段的就绪/交付计数，后者按各自真实阶段累计开销；不跨阶段继承Y或按跳数倍计。 |
| $L_e,L_m$ 与 $B_\ell,B_{\mathrm{seq}}$ | GPU名额/模型层数、bit/s容量/无量纲序列维度均已区分。 |
| $\delta,\delta_{\mathrm{cool}},\delta_{s,n}^{\mathrm{HO}}$ | bit/s填充增量、秒级冷却、秒级实际接入延期，完整符号不同。 |

未发现完全相同的完整符号被定义成两个不同物理量。对若干先在式中出现、紧接式后解释的量，保留其正常定义式写法；另外将GPU服务速率、SLA预警时间、STOP/Cutover/解冻时刻及优先级组集合的必要说明前移，不更名或改变其公式。

## 九、全部编号公式逐式复核

| 公式 | 量纲、定义域与接口核查 |
|---|---|
| (1) | bit/s=Hz×无量纲；与前后相应定义及执行边界一致。 |
| (2) | 有向连接上的bit/s求和；与前后相应定义及执行边界一致。 |
| (3) | 剩余bit/s÷流数得到bit/s增量；与前后相应定义及执行边界一致。 |
| (4) | Byte导数=bit/s÷8；与前后相应定义及执行边界一致。 |
| (5) | s=s+序号×s；与前后相应定义及执行边界一致。 |
| (5a) | 无量纲概率，行和1；与前后相应定义及执行边界一致。 |
| (5b) | 事件序列；计划Access为Edge；与前后相应定义及执行边界一致。 |
| (5c) | s，实际生效不早于计划；与前后相应定义及执行边界一致。 |
| (5d) | s，完成者定义且非负；与前后相应定义及执行边界一致。 |
| (6) | 模型/优先级固定映射；与前后相应定义及执行边界一致。 |
| (7) | Turn输入输出序列与移动事件序列；与前后相应定义及执行边界一致。 |
| (8) | s，零Idle仅指提交；与前后相应定义及执行边界一致。 |
| (9) | token累计与上限；与前后相应定义及执行边界一致。 |
| (10) | token历史、输入、输出上界；与前后相应定义及执行边界一致。 |
| (11) | token全量合法负载充分条件；与前后相应定义及执行边界一致。 |
| (12) | Byte；每Token为Byte/token；与前后相应定义及执行边界一致。 |
| (13) | token与Byte分别守恒；与前后相应定义及执行边界一致。 |
| (14) | Byte=Byte/token×token；与前后相应定义及执行边界一致。 |
| (15) | eq-work及部分工作守恒；与前后相应定义及执行边界一致。 |
| (16) | Turn数与eq-work/s双约束；与前后相应定义及执行边界一致。 |
| (17) | eq-work/s等份；与前后相应定义及执行边界一致。 |
| (18) | eq-work=服务速率时间积分；与前后相应定义及执行边界一致。 |
| (19) | s，指示函数时间积分；与前后相应定义及执行边界一致。 |
| (20) | 字典序受害者与二元名额转换；与前后相应定义及执行边界一致。 |
| (21) | Byte净容量与权威和；与前后相应定义及执行边界一致。 |
| (22) | s，UE完整交付事件定义；与前后相应定义及执行边界一致。 |
| (23) | s，预警比例无量纲；与前后相应定义及执行边界一致。 |
| (23a) | 布尔申请，实际Access变化；与前后相应定义及执行边界一致。 |
| (24) | 0/1目标及模型兼容；与前后相应定义及执行边界一致。 |
| (25) | Byte前缀/Shadow/承诺及容量；与前后相应定义及执行边界一致。 |
| (26) | Byte启动完整KV承诺；与前后相应定义及执行边界一致。 |
| (27) | Byte尾部与事件增量守恒；与前后相应定义及执行边界一致。 |
| (28) | Byte/s；bit/s除8，token/s乘Byte/token；与前后相应定义及执行边界一致。 |
| (29) | 布尔准入及Byte÷Byte/s得到s；与前后相应定义及执行边界一致。 |
| (30) | Byte冻结量和固定尾部；与前后相应定义及执行边界一致。 |
| (31) | Byte同步、s真实中断、Edge权威更新；与前后相应定义及执行边界一致。 |
| (32) | s失败中断及无量纲STOP计数；与前后相应定义及执行边界一致。 |
| (33) | 因果观测到布局映射；与前后相应定义及执行边界一致。 |
| (34) | Turn数，全量分母正；与前后相应定义及执行边界一致。 |
| (35) | s，总完整E2E÷Turn数；与前后相应定义及执行边界一致。 |
| (36) | Byte迁移和Byte·s Shadow积分；与前后相应定义及执行边界一致。 |
| (37) | Byte/Turn、Byte·s/Turn；与前后相应定义及执行边界一致。 |
| (37a) | Byte，仅真实额外转发阶段；与前后相应定义及执行边界一致。 |
| (38) | s，期望在共同完整交付评价域有定义；与前后相应定义及执行边界一致。 |
| (39) | Turn数守恒和无量纲完成率；与前后相应定义及执行边界一致。 |
| (40) | 二元违约及组比例；与前后相应定义及执行边界一致。 |
| (41) | 二元计算资格与唯一权威；与前后相应定义及执行边界一致。 |
