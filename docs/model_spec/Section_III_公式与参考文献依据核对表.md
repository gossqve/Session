# Section III 公式与参考文献依据核对表

核查日期：2026-11-03。源文件取自本次上传《建模文档.zip》，原稿未覆盖。A指Problem Description；B指Network；C1指Session；C2指GPU/Edge；D指Joint Re-placement；E指压缩包内“六项确认修订版”。本次未提供另名“接口核查修订版”或独立接口报告，依任务prompt的权威要求自行核查并整合。

依据类型：[A]原文直接支持机制；[B]相关背景；[C]数学定义、张量维度或守恒推导；[D]本文仿真假设。组合类型不表示文献直接给出本文精确公式；正文中的“本文采用”“定义”“推导”用于区分这些性质。下表引用统一为正文编号。

## 一、全部编号公式

| 公式/机制 | 所在章节 | 对应源文档 | 参考文献及链接 | 依据类型 | 核查结果 |
|---|---|---|---|---|---|
| (1) 无线有效速率 | B | B | [4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (2) 有向链路容量 | B | B | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (3) 渐进填充残余容量与步长 | B | B | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | A/C/D | 原文支持主要机制；本文符号、参数及组合另作定义 |
| (4) 网络字节供给及速率换算 | B | B | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (5) Turn级接入位置与移动间隔 | B、C | B/C1 | [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (6) 固定模型和优先级 | C | C1 | 无外部引文；依定义/守恒或本文规则 | D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (7) 多轮预生成工作负载 | C | C1 | [5](https://doi.org/10.1145/3689031.3696086)；[6](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost) | B/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
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
| (38) 平均完整Turn时延主目标 | E | E | 无外部引文；依定义/守恒或本文规则 | D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (39) 完成度与未完成分解 | E | E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (40) 真实SLA违约与分组统计 | D、E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |
| (41) 唯一权威GPU计算资格 | C、D、E | C2/D/E | 无外部引文；依定义/守恒或本文规则 | C/D | 已核对定义域、单位与源稿；精确式属本文定义/推导或假设 |

## 二、非公式关键机制

| 公式/机制 | 所在章节 | 对应源文档 | 参考文献及链接 | 依据类型 | 核查结果 |
|---|---|---|---|---|---|
| 三域直连、全双工固定路径、逻辑边界只转发 | A/B | A/B | 本文规则，无强行外引 | D | 本文拓扑假设；未宣称外部文献逐字验证 |
| 独立有效无线、不模拟RTT/控制字节/逐跳缓存 | B | B | [4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | B/D | 对数无线速率有据；排除项是本文简化 |
| 按Turn响应持续队列及Copy公平，切换共享连接去重 | B | B | [3](https://www.rfc-editor.org/rfc/rfc5166.html) | B/D | 不是逐Token多份额；复杂分支合流语义见检查报告 |
| Token完整到Access后无线发送、FIFO及Decode流水 | B/C | B/C1 | [9](https://www.usenix.org/conference/osdi22/presentation/yu)；[10](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | B/D | 迭代和仿真有背景；两级交付接口为本文规则 |
| 固定绑定、零Idle、未来不可见、Turn级外生移动 | B/C | B/C1 | [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process)；[5](https://doi.org/10.1145/3689031.3696086) | B/D | Pensieve包含Think Time；不将零Idle或Turn移动归于文献 |
| 统一累计等待排序、同刻更新、同级不抢占 | C | C2 | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[15](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang)；[20](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | B/D | 源稿局部FCFS表述按详细累计等待排序统一 |
| KVBlocked保存满阈值部分服务、不提交、不重复计算 | C | C2 | [7](https://arxiv.org/abs/2309.06180) | B/C/D | 有限KV背景；恢复与阻塞执行是本文定义 |
| 四类Check、冷却待办、容量安全绕过 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/D | 未把本文触发和合并机制说成Llumnix原算法 |
| 初始/增量在线复制、末段冻结、目标预分配 | D | D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | A/D | 核对Llumnix §4.2及Fig.6–7、Clark阶段机制 |
| 排队输入真实交接、Prefill完成、Decode完整Token边界 | C/D | B/C2/D | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | B/D | 本文安全接口；无免费输入传输或Kernel迁移 |
| STOP跨Turn仍提交，但实际上传延期 | C/D | B/C1/C2/D | 本文规则，无强行外引 | D | 不改提交时间，不向旧源制造新在途输入 |
| 复用/延后/取消、唯一ID、失败历史成本保留 | D/E | D/E | [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao)；[16](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | B/C/D | 同会话禁止冲突Copy；历史集与活动集分开 |
| 全量合法Turn分母、未完成不可伪造完整均值 | E | C1/E | 本文规则，无强行外引 | C/D | 目标仅在指标有定义的评价范围适用，非所有安全策略完整排序 |
| SLA预警保留但非硬约束；成本统计非成本优化保证 | D/E | D/E | 本文规则，无强行外引 | D | 按用户六项确认，不另加权重、预算、罚分 |

## 三、正文文献在线核查与引用范围

| 编号 | 在线状态与核查材料 | 准确支持范围 |
|---|---|---|
| [1](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | 已在线读取上述一手材料；官方会议页与PDF §4.2、Fig.6–7；KV追加式在线复制、预分配、清理；不保证本模型跨域性能 | 仅限所列机制；未逐字移植公式 |
| [2](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | 已在线读取上述一手材料；IBM作者机构页面核对标题、作者、2019年；支持移动服务位置取舍，不支撑本文Turn移动原式 | 仅限所列机制；未逐字移植公式 |
| [3](https://www.rfc-editor.org/rfc/rfc5166.html) | 已在线读取上述一手材料；RFC §2.3.2核对Progressive Filling；Informational，并非本系统必须遵循的标准 | 仅限所列机制；未逐字移植公式 |
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

以下由六份原稿全文提取并按URL合并；同文不同URL仍列出用于追溯。未纳入正文的重复、背景或实验配置候选不作为正文已核验依据，不等于认定其错误。没有取得内容的候选统一标为“未在线核验”，不推断发表状态。

| 原始链接 | 出现于源稿 | 正文去向/核验状态 |
|---|---|---|
| [链接](https://aclanthology.org/2023.emnlp-main.298/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[8]；核验范围见上表 |
| [链接](https://arxiv.org/abs/1506.05261) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/abs/1706.03762) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/abs/1809.05239) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/abs/2309.06180) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[7]；核验范围见上表 |
| [链接](https://arxiv.org/abs/2405.05465) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/abs/2603.28018) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/abs/2608.10545) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/html/2312.05516) | Stateful_AI_Session_Re-placement_Session_Model.md | [5]已在线核验作者全文 |
| [链接](https://arxiv.org/html/2406.03243) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/html/2603.28018) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://arxiv.org/html/2608.10545) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://conferences.sigcomm.org/sigcomm/2013/papers/sigcomm/p15.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://datatracker.ietf.org/doc/html/rfc5166) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://developer.nvidia.com/blog/memory-enforced-gpu-sharing-in-kubernetes-with-nvidia-cuda-13-4/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[13]；核验范围见上表 |
| [链接](https://docs.nvidia.com/knowledge-base/latest/vgpu-features.html) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://docs.nvidia.com/run-ai/self-hosted/v3.0/documentation/platform-management/runai-scheduler/resource-optimization/gpu-fractions/compute-modes) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[14]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/latest/api/vllm/config/cache/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[21]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/latest/api/vllm/config/model/) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[18]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[20]；核验范围见上表 |
| [链接](https://docs.vllm.ai/en/stable/api/vllm/sampling_params/) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[19]；核验范围见上表 |
| [链接](https://doi.org/10.1002/spe.2755) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://doi.org/10.1016/j.future.2016.05.003) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://doi.org/10.1109/TNET.2002.1012364) | Stateful AI Session Re-placement：Network Model.md | DOI工具无法访问；正文改引已核验RFC，未在线核验该论文全文 |
| [链接](https://doi.org/10.1109/TWC.2023.3290005) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://doi.org/10.1145/2486001.2486012) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://doi.org/10.1145/3600006.3613165) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | [7]DOI直达403，改用作者公开版本交叉核验 |
| [链接](https://doi.org/10.1145/3689031.3696086) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[5]；核验范围见上表 |
| [链接](https://github.com/vllm-project/vllm/blob/main/benchmarks/multi_turn/README.md) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://huggingface.co/Qwen/Qwen3-4B/blob/main/config.json) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation) | Stateful_AI_Session_Re-placement_Session_Model.md | 正文[17]；核验范围见上表 |
| [链接](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/config.json) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://ieeexplore.ieee.org/document/10173745/) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://onlinelibrary.wiley.com/doi/full/10.1002/spe.2755) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/) | Stateful AI Session Re-placement：Network Model.md | 正文[4]；核验范围见上表 |
| [链接](https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[11]；核验范围见上表 |
| [链接](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[10]；核验范围见上表 |
| [链接](https://proceedings.nips.cc/paper_files/paper/2024/hash/724be4472168f31ba1c9ac630f15dec8-Abstract-Conference.html) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[2]；核验范围见上表 |
| [链接](https://shiqiang.wang/papers/WS_Networking2015.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://team.inria.fr/rap/files/2013/12/MR02.pdf) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.lk.cs.ucla.edu/data/files/Kleinrock/Processor%20Sharing%20Queueing%20Models%20of%20Mixed.pdf) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.nature.com/articles/s41598-026-36711-y) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.nvidia.cn/geforce/graphics-cards/compare/) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.rfc-editor.org/rfc/rfc5166.html) | Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[3]；核验范围见上表 |
| [链接](https://www.sciencedirect.com/science/article/pii/S0167739X16301133) | Stateful AI Session Re-placement：Network Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[6]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 正文[15]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi22/presentation/yu) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[9]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/agrawal) | Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/sun-biao) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_GPU_计算调度与KV显存资源模型_最终修订与论文依据_2026-10-31.md<br>Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md<br>Stateful_AI_Session_Re-placement_Session_Model.md | 正文[1]；核验范围见上表 |
| [链接](https://www.usenix.org/conference/osdi24/presentation/zhong-yinmin) | Stateful_AI_Session_Re-placement_Session_Model.md | 未纳入正文；未在线核验，保留追溯 |
| [链接](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html) | Stateful_AI_Session_Re-placement_D_Joint_Re-placement_Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | 正文[16]；核验范围见上表 |
| [链接](https://www.usenix.org/system/files/osdi24-sun-biao.pdf) | Stateful AI Session Re-placement：Network Model.md<br>Stateful_AI_Session_Re-placement_E_Problem_Formulation_六项确认修订稿_2026-11-03.md | [1]已在线核验全文 |
