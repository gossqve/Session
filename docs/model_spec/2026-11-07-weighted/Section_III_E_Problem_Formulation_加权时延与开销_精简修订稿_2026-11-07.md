## E. Problem Formulation

前述网络、会话资源与联合重放置模型表明，会话的目标执行位置决定其后续推理服务所使用的传输路径及边缘计算资源，而执行位置的实际改变还需要经历非瞬时的 KV 状态复制与安全切换。因而，仅考虑目标布局所对应的服务时延，无法同时衡量执行位置调整所引入的额外资源消耗。为此，本文将在线联合会话重放置表述为服务时延与执行调整开销的联合优化问题。设 $\pi$ 为在线重放置策略，策略在第 $j$ 次联合检查时，仅根据可观测状态 $\mathcal O_j$ 为全部存活会话确定目标布局 $\boldsymbol z_j=\pi(\mathcal O_j)$；实际执行位置仍须遵守 D 节规定的容量承诺、状态同步及原子切换过程。

首先，考虑完整推理服务的端到端响应时延。对会话 $s$ 的第 $k$ 个 Turn，记 $q=(s,k)$，$t_q^{\mathrm{sub}}$ 为该轮请求提交时刻，$t_q^{\mathrm{recv}}$ 为最后一个有效响应 Token 完整到达用户的时刻。其完整端到端时延定义为

$$
D_q^{\mathrm{E2E}}=t_q^{\mathrm{recv}}-t_q^{\mathrm{sub}}.\tag{14}
$$

式 (14) 覆盖从请求提交到响应完整交付之间实际发生的无线与有线传输、计算与就绪等待、显存阻塞、迁移冻结，以及接入切换所造成的响应接续与顺序等待。由于 Decode 与已生成 Token 的下行传输能够重叠，在线 KV 复制也可与源端计算并行，故以实际完成时刻计算完整 Turn 时延，而不直接累加各阶段持续时间。本文不在相邻 Turn 之间引入用户思考时间；下一轮仅在上一轮完整交付后提交。因此，式 (14) 不包含提交前的轮次间空闲，却保留所有影响本轮实际响应时间的合法等待。对于给定工作负载 $\omega$，令 $\mathcal Q^{\mathrm{all}}(\omega)$ 表示全部计划合法 Turn 的集合，$N_{\mathrm{turn}}(\omega)=|\mathcal Q^{\mathrm{all}}(\omega)|$；当这些 Turn 均完整交付时，以 $\overline D^{\mathrm{E2E}}(\pi;\omega)$ 表示其 $D_q^{\mathrm{E2E}}$ 的算术平均值。

其次，联合重放置除了改变实际服务时延，还会引起额外资源开销。令 $V^{\mathrm{mig}}(\pi;\omega)$ 表示评价期间实际发送的 KV 状态复制字节数，$A^{\mathrm{shadow}}(\pi;\omega)$ 表示目标端已物化 Shadow KV 的累计显存占用时间（Byte·s），$V^{\mathrm{HO}}(\pi;\omega)$ 表示因 Access Handover 产生的额外普通响应转发字节数。综合开销定义为

$$
C(\pi;\omega)=
\beta_{\mathrm{mig}}V^{\mathrm{mig}}(\pi;\omega)
+\beta_{\mathrm{sh}}A^{\mathrm{shadow}}(\pi;\omega)
+\beta_{\mathrm{HO}}V^{\mathrm{HO}}(\pi;\omega).\tag{15}
$$

其中，$\beta_{\mathrm{mig}}$、$\beta_{\mathrm{sh}}$ 和 $\beta_{\mathrm{HO}}$ 为非负开销折算系数，用于将 Byte 与 Byte·s 转换至统一的代价尺度。三项仅依据实际发生的复制流量、物化 Shadow 驻留以及额外转发流量计量；迁移取消或失败前已产生的开销同样保留，尚未物化的目标容量承诺不计入 Shadow 占用。迁移引发的传输竞争和冻结等待已经反映在式 (14) 的时延中，式 (15) 则从资源消耗角度刻画其代价，并非额外增加一段响应时延。

基于上述两个指标，本文在共同评价工作负载集合 $\Omega_{\mathrm{eval}}$ 上，最小化平均完整 Turn 时延与综合开销的加权和：

$$
\min_{\pi\in\Pi_{\mathrm{safe,full}}}
\mathbb E_{\omega}\!\left[
\omega_1\overline D^{\mathrm{E2E}}(\pi;\omega)
+\omega_2 C(\pi;\omega)
\right].\tag{16}
$$

式中，$\omega_1,\omega_2\ge0$ 为时延与综合开销的权重，其数值及单位尺度在实验设置中统一给定，以保证两项可以进行有意义的加权比较；$\mathbb E_{\omega}$ 按共同评价工作负载的既定分布求期望。$\Pi_{\mathrm{safe,full}}$ 表示仅利用当前及历史信息、满足下述物理与迁移安全条件，并在共同评价口径下完整交付全部计划合法 Turn、从而使平均完整时延有定义的策略集合。该完成性限定是式 (16) 的定义域要求，而非运行时允许强制恢复或忽略失败会话。若某次运行存在未完成 Turn，则不以完成者均值代替全量均值，而应另行报告完成情况和删失信息。移动计划对不同策略采用共同外生输入，但因接入保护和响应接续不同，实际 Handover 时刻仍可能随策略变化。

为保证上述优化目标对应可实施的联合布局，首先要求每次检查为每个存活会话指定唯一且已部署其绑定模型的目标节点：

$$
\sum_{e\in\mathcal E}z_{s,e,j}=1,\qquad
z_{s,e,j}\le x_{e,m_s},\qquad
z_{s,e,j}\in\{0,1\},\quad
\forall s\in\mathcal S(t_j),\ e\in\mathcal E.\tag{17}
$$

式 (17) 保证目标选择的唯一性与模型兼容性，但计划目标 $z_{s,e,j}$ 不会立即改变实际执行位置 $y_s(t)$；成功 Cutover 前源端始终保存唯一权威 KV。对任一 Edge $e$，其同时运行 Turn 数及所分配的 GPU 服务速率还需满足

$$
\left|\mathcal Q_e^{\mathrm{run}}(t)\right|\le L_e,\qquad
\sum_{q\in\mathcal Q_e^{\mathrm{run}}(t)}c_{q,e}(t)
\le C_e^{\mathrm{GPU}},\quad \forall e\in\mathcal E.\tag{18}
$$

该约束限制节点的并发计算名额与总计算服务预算；运行 Turn 的具体份额仍由 C 节的等权共享规则确定，同一 Turn 只能在当前权威执行节点获得计算服务。另一方面，权威 KV 和在途迁移的目标端容量承诺必须共同受净 KV 显存限制：

$$
U_e^{\mathrm{KV}}(t)
+\sum_{\mu\in\mathcal I_e(t)}Q_\mu(t)
\le C_e^{\mathrm{KV}},\qquad \forall e\in\mathcal E.\tag{19}
$$

式 (19) 中 $Q_\mu(t)$ 已包含实际物化的 Shadow，不得重复计入。任何新增 KV 的合法提交均须满足此容量约束；容量不足时保留已形成状态并暂停相关计算。会话累计上下文和单轮输出长度仍受 C 节式 (5) 限制，不允许因位置调整而清零或越界增长。

最后，普通请求、流式响应、Handover 附加转发及 KV Copy 共享其实际经过的有向链路，并满足

$$
\sum_{f\in\mathcal F(t):\,\ell\in\mathcal P_f}r_f(t)
\le B_\ell,\qquad \forall\ell\in\mathcal L.\tag{20}
$$

其中，各活动流的非负速率由 B 节所述无权 Max-Min 机制确定，反向链路独立受限。合法 Access 与实际 Execution 之间必须具备普通请求及响应的固定有向传输路径；Access Handover 还须满足无线 Token、输入传输及旧响应接续的保护条件，保证完整交付和 Token 顺序。对于实际 KV 迁移，目标端须先承诺当前全部已有 KV，初始复制完成且满足输入与计算安全边界后，才能按 D 节式 (12) 的尾部准入条件进入 Stop-and-Copy；只有取得一致的完整状态并完成安全交接，才能依照式 (13) 原子更新 Execution Edge。同一会话不得向冲突目标并发复制，在途操作的失败、取消与跨检查协调均不得破坏唯一权威状态。

综上，式 (16) 在模型兼容、计算与显存容量、网络带宽及状态一致性条件下，统一权衡完整 Turn 的响应时延与联合重放置的实际资源开销，为后续在线决策方法提供优化依据。
