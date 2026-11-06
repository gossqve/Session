## A. Problem Description

本文考虑由多个服务区域组成的移动边缘大语言模型（Large Language Model，LLM）推理系统，每个区域包含若干边缘服务器（Edge）。基础拓扑为三个区域两两直连，区域集合为 $\mathcal R$，区域 $r$ 的服务器集合为 $\mathcal E_r$，全部服务器组成 $\mathcal E=\bigcup_{r\in\mathcal R}\mathcal E_r$。候选模型集合为 $\mathcal M$，固定部署矩阵 $x_{e,m}$ 表示服务器 $e$ 是否预部署模型 $m$。移动用户通过无线链路连接当前接入服务器（Access Edge），创建状态化LLM会话（Session）。会话在创建时固定绑定模型，连续处理多个对话轮次（Turn），并保留随实际推理增长的键值缓存（KV Cache）。负责推理并保存唯一权威KV的服务节点（Execution Edge）可以与接入节点不同。多轮历史状态复用与运行期请求重调度分别具有文献[5]–[7]及[1]的研究基础；本文采用固定模型部署和固定会话绑定。

新会话到达后，系统根据模型兼容、初始KV容量与网络可达性确定初始服务节点；GPU运行名额暂满时允许合法排队。当一轮完整响应抵达用户后，下一轮立即提交。用户移动改变接入节点，但不自动改变权威服务节点；二者不同时，普通请求与响应需通过有线网络转发。多个会话共同竞争GPU等效计算能力、同时运行名额、KV显存及有向链路带宽。迁移一个会话需要同步完整历史KV和复制期间真实新增的KV，占用源端与目标端资源并影响其他业务。因此，移动条件下的服务调整既涉及通信路径，也涉及计算竞争和迁移过程的状态安全，而非仅改变一个位置标记。移动服务位置与迁移代价之间的取舍可参考文献[2]，本文进一步考虑多轮LLM状态和多会话资源耦合。

针对上述问题，本文研究在线联合会话重放置（Joint Session Re-placement）。在有效移动、当前Turn首次SLA预警、实际KV显存压力及低频周期检查时，系统依据当前与历史可观测状态，联合选择所有存活会话的目标服务节点，允许保持布局、调整单个会话或联合调整多个会话。新会话到达只进行初始接纳与放置，不直接触发全域调整。目标改变通过在线KV复制与安全切换实现，并与已有在途迁移协调。本文在模型兼容、计算、显存、网络及状态一致性约束下，以平均完整Turn端到端响应时延最小化为主要优化目标；实际KV传输量和影子缓存驻留开销分别记录与报告，不将其预设为加权目标或硬预算。

表Ⅰ列出主要基础符号，其余状态量在首次出现时定义。除特别说明外，时间单位为秒，存储与数据量单位为Byte，有线及无线速率单位为bit/s。

| 符号 | 定义 | 单位或取值 |
|---|---|---|
| $\mathcal R,\mathcal E_r,\mathcal E,\mathcal M$ | 区域、区内Edge、全部Edge、候选模型集合 | 集合 |
| $\rho(e),x_{e,m}$ | Edge所属区域、固定模型部署标记 | 区域；$\{0,1\}$ |
| $\mathcal S(t),q=(s,k),J_s$ | 存活会话集合、第$k$轮Turn、会话计划总轮数 | 集合；索引；Turn |
| $m_s,p_s$ | 固定绑定模型和优先级 | 模型；$\mathrm H/\mathrm L$ |
| $a_s(t),y_s(t),z_{s,e,j}$ | 当前接入、实际权威服务节点、第$j$次检查的目标指派 | Edge；Edge；$\{0,1\}$ |
| $C_e^{\mathrm{GPU}},L_e,C_e^{\mathrm{KV}}$ | 等效计算预算、同时运行名额、净KV容量 | eq-work/s；Turn；Byte |
| $w_m^{\mathrm{pre}},w_m^{\mathrm{dec}}$ | 输入及输出Token的等效工作量系数 | eq-work/token |
| $\mathcal L,B_\ell,\mathcal P_f,r_f(t)$ | 有向有线连接集、容量、固定传输路径、有线传输速率 | 集合；bit/s；路径；bit/s |
| $W_s^d,\gamma_s^d,\eta_s^d,R_s^d$ | 方向$d$的有效无线带宽、线性SNR、折减系数及速率 | Hz；无量纲；无量纲；bit/s |
| $N_m^{\mathrm{ctx,max}},N_{\max}^{\mathrm{out}}$ | 模型累计上下文上限、单Turn新增输出上限 | token |
| $b_m^{\mathrm{KV}},b^{\mathrm{text}},K_s(t)$ | 单Token KV字节、文本换算字节、权威KV大小 | Byte/token；Byte/token；Byte |
| $D^{\max},\theta,\delta_{\mathrm{cool}},\Delta_{\mathrm{check}}$ | SLA阈值、预警比例、普通检查冷却及周期 | s；$(0,1)$；s；s |
| $\Delta_{\min}^{\mathrm{move}}$ | 连续有效移动的最小Turn序号间隔 | Turn |
| $I_{\max}^{\mathrm{mig}},M_{\max}^{\mathrm{mig}}$ | 普通迁移预计冻结预算、累计STOP次数上限 | s；次 |

## B. Network Model

### 1. 固定路径与独立无线接入

令 $\rho(e)$ 表示节点所属区域。区域内已配置Edge对使用有向逻辑连接，跨区域路径采用源Edge出口、直接区域互联和目标Edge入口。以 $g_r$ 表示区域 $r$ 的逻辑转发边界，则跨域路径可表示为 $e\to g_r\to g_{r'}\to e'$；$g_r$ 不承担模型服务，不属于 $\mathcal E$。所有有向连接构成 $\mathcal L$，每条连接 $\ell$ 具有容量 $B_\ell>0$，反向连接容量独立，基础场景不经过第三域中转。区内已配置直连时使用对应路径，未配置连接不视为无限速可达。这些拓扑和全双工容量是本文的网络抽象，不设置额外的区域总带宽池或Edge整机NIC共享瓶颈，也不动态优化路由。

对会话 $s$ 的无线方向 $d\in\{\mathrm{up},\mathrm{down}\}$，采用基于Shannon–Hartley关系的有效速率模型[4]：

$$
R_s^d(t)=\eta_s^d(t)W_s^d(t)\log_2\!\left(1+\gamma_s^d(t)\right),
\qquad 0<\eta_s^d(t)\le1.\tag{1}
$$

$W_s^d$ 是已分配给该用户的有效带宽，$\gamma_s^d$ 为线性SNR，$\eta_s^d$ 是本文采用的实现折减系数。多用户的无线速率独立给定，不重复解释为每个用户独占整个基站频谱，也不参与有线公平分配。无线频谱调度、RTT、传播、协议额外字节、丢包重传和逐跳分组缓存均不纳入当前模型；控制通知与小型切换元数据也不单独计时或占带宽。

普通上行依次经过UE→Access和必要的Access→Execution有线路径；下行方向相反。当 $a_s(t)=y_s(t)$ 时，普通业务只占无线，不创建Edge间有线传输。远程服务不自动复制KV。迁移流只沿Source→Target的固定有线路径传输，不使用UE无线。

### 2. 有线Max-Min分配与真实字节推进

令 $f$ 为有线传输任务索引，$\mathcal F(t)$ 为已启动且有待发字节的任务集合，$\mathcal P_f\subseteq\mathcal L$ 为固定路径，$r_f(t)$ 为端到端有线速率。链路容量要求为

$$
\sum_{f\in\mathcal F(t):\,\ell\in\mathcal P_f}r_f(t)\le B_\ell,
\qquad r_f(t)\ge0,\quad \ell\in\mathcal L.\tag{2}
$$

请求转发、响应、普通输入交接与KV复制共享相同的有向容量约束。本文固定采用无权Max-Min Progressive Filling，文献[3]给出从零等幅增长、遇路径瓶颈后冻结的公平分配思想；本文的拓扑、业务粒度和无权选择是具体仿真假设。一次重算从 $r_f=0$ 开始，令 $\mathcal U$ 为尚未冻结的传输集合：

$$
\begin{aligned}
C_\ell^{\mathrm{res}}&=B_\ell-\sum_{f:\,\ell\in\mathcal P_f}r_f,\\
\nu_\ell&=\left|\{f\in\mathcal U:\ell\in\mathcal P_f\}\right|,\\
\delta&=\min_{\ell:\,\nu_\ell>0}\frac{C_\ell^{\mathrm{res}}}{\nu_\ell}.
\end{aligned}\tag{3}
$$

每个未冻结任务同时增加 $\delta$，冻结经过新饱和连接的任务，直至 $\mathcal U$ 为空。已冻结速率继续占用其所有路径连接，其他任务利用剩余容量；$\nu_\ell=0$ 的连接不参与除法，空集合不分配速率。该规则允许回收其他瓶颈造成的未用容量，不能替换为逐连接一次均分再取最小值。

一个Turn在每个实际路径段上的响应使用持续待发队列，后续Token只增加就绪字节，不新增公平份额；KV复制和输入交接分别为独立任务。切换前后的同一Turn响应若共享某有向连接，在该连接上合并计为一项公平竞争流，而不按Token或旧、新源重复申请份额。路径分支保留已就绪字节的来源及交付进度，只有尚有待发字节的路径段参与竞争。GPU高低优先级不改变网络权重。

为避免网络累计供给量与GPU累计等待量重名，以 $G_f(t)$ 表示当前传输段累计已就绪Byte，以 $Y_f(t)$ 表示累计已交付Byte，则

$$
0\le Y_f(t)\le G_f(t),\qquad
\frac{\mathrm dY_f(t)}{\mathrm dt}=\frac{r_f(t)}8
\quad\text{（存在待发字节且速率为正时）}.\tag{4}
$$

队列为空或速率为零时推进量为零；无线段以 $R_s^d/8$ 同样推进。常速下传输 $V$ Byte的时间为 $8V/r_f$。传输加入、完成、取消、合法路径归属改变或待发队列空/非空转换时重算速率，各事件间只推进到最早的下一事件。完整有线路径采用一个端到端流体速率，不模拟内部逐跳缓存。一份KV经过多条容量受限连接，只产生一次逻辑复制字节量，不按跳数重复计入迁移开销。

### 3. 流式响应与Turn级移动

普通文本用固定系数 $b^{\mathrm{text}}$ 换算；该系数是实验抽象，不代表所有模型的真实编码。第 $h$ 个输出Token在 $t_{q,h}^{\mathrm{gen}}$ 合法提交后才产生待发字节。Execution不同于Access时，完整Token先经有线抵达Access，再排入无线下行；不同Token可流水传输并与Decode重叠，自回归迭代服务与事件仿真背景见文献[9][10]。同一Turn按FIFO顺序交付，切换后的较新Token不得越过尚在原路径上的更早Token。请求上行则采用完整输入先无线、再必要有线转发的简化，不建立输入Token跨段流水。

接入位置由预生成的Turn级序列 $a_{s,k}^{\mathrm{plan}}$ 决定：

$$
\begin{aligned}
a_s(t)&=a_{s,k}^{\mathrm{plan}},
&&t\in[t_{s,k}^{\mathrm{sub}},t_{s,k}^{\mathrm{recv}}),\\
k_{i+1}-k_i&\ge\Delta_{\min}^{\mathrm{move}}\ge1.
\end{aligned}\tag{5}
$$

$k_i$ 是发生有效Access变化的轮次序号。上一轮完整交付后，依次更新下一轮Access、登记有效移动检查申请并立即提交下一轮，时间戳相同。移动仅改变Access，后台复制可跨越该边界。所有算法复用相同的会话与Turn级轨迹，未来位置对在线策略不可见；不再施加秒级驻留限制。文献[2]提供外生移动与服务迁移的背景，将更新边界选择为LLM Turn是本文简化。该规则保证相同Turn序号的接入一致，不保证相同绝对时间的位置、每秒移动率或实际完成移动总数一致；截尾运行只经历共同序列的前缀。

## C. Session and Edge Resource Model

### 1. 生命周期与预生成多轮工作负载

以 $t_s^{\mathrm{arr}}$ 表示会话到达时刻，$\mathcal S(t)$ 表示尚未终止的会话集合。创建时由已有R2A选择器根据初始请求 $q_s^{\mathrm{initial}}$ 固定绑定模型，并确定高、低优先级：

$$
m_s=\operatorname{R2A}(q_s^{\mathrm{initial}}),\qquad
p_s\in\{\mathrm H,\mathrm L\},\qquad
m_s(t)=m_s,\quad p_s(t)=p_s.\tag{6}
$$

固定绑定、优先级及部署不作为运行期动作。每个会话串行处理Turn，同一时刻最多一个未完成请求。多轮历史KV复用具有文献[5][6]支持，本文预生成工作负载为

$$
\mathcal W_s=\left\{
\bigl(n_{s,k}^{\mathrm{in}},\widetilde n_{s,k}^{\mathrm{out}},a_{s,k}^{\mathrm{plan}}\bigr)
\right\}_{k=1}^{J_s}.\tag{7}
$$

$J_s$ 为总轮数，$n_{s,k}^{\mathrm{in}}$ 为新增输入长度，$\widetilde n_{s,k}^{\mathrm{out}}$ 为仿真器隐藏的计划输出长度。令 $q=(s,k)$，相应量可简写为 $n_q^{\mathrm{in}}$ 等；$n_q^{\mathrm{out}}$ 是最终实际输出，带 $\mathrm{done}$ 的量为截至当前已合法提交的Token数。跨算法固定到达时刻、绑定模型、优先级及完整负载样本；在线只读取已提交输入和已生成内容，不读取最终输出长度、未来轮数或未来移动。

令 $t_q^{\mathrm{sub}}$ 和 $t_q^{\mathrm{recv}}$ 为Turn提交和完整交付时刻。当前采用零轮间等待：

$$
t_{s,k+1}^{\mathrm{sub}}=t_{s,k}^{\mathrm{recv}},\qquad k<J_s.\tag{8}
$$

零间隔是本文设定，不照搬文献[5]中的用户思考时间。输入到达Execution后进行新增输入Prefill，复用历史KV，再逐Token Decode；生成结束与完整响应交付是不同事件。

### 2. 累计Context与KV增长

模型原生累计上下文上限记为 $N_m^{\mathrm{ctx,max}}$，单Turn新增输出上限为 $N_{\max}^{\mathrm{out}}$，二者含义分别与模型最大长度及生成长度配置相对应[18][19]。令 $n_{s,k}^{\mathrm{in,done}}(t)$ 和 $n_{s,k}^{\mathrm{out,done}}(t)$ 为实际完成并提交的输入、输出Token计数：

$$
N_s^{\mathrm{ctx}}(t)=\sum_{k=1}^{J_s}
\left[n_{s,k}^{\mathrm{in,done}}(t)+n_{s,k}^{\mathrm{out,done}}(t)\right]
\le N_{m_s}^{\mathrm{ctx,max}},\qquad
0\le n_{s,k}^{\mathrm{out}}\le N_{\max}^{\mathrm{out}}.\tag{9}
$$

未开始轮次贡献为零，Context不在每轮清零。令 $N_{s,k}^{\mathrm{hist}}$ 为本轮开始前缓存的历史Token数，新增输入可完整容纳时：

$$
\begin{aligned}
N_{s,k}^{\mathrm{hist}}+n_{s,k}^{\mathrm{in}}&\le N_{m_s}^{\mathrm{ctx,max}},\\
n_{s,k}^{\mathrm{out}}&\le\min\left\{
\widetilde n_{s,k}^{\mathrm{out}},N_{\max}^{\mathrm{out}},
N_{m_s}^{\mathrm{ctx,max}}-N_{s,k}^{\mathrm{hist}}-n_{s,k}^{\mathrm{in}}
\right\}.
\end{aligned}\tag{10}
$$

为构造全量计划合法的有限评估负载，可离线采用充分筛选条件：

$$
\sum_{k=1}^{J_s}\left[n_{s,k}^{\mathrm{in}}+
\min\{\widetilde n_{s,k}^{\mathrm{out}},N_{\max}^{\mathrm{out}}\}\right]
\le N_{m_s}^{\mathrm{ctx,max}}.\tag{11}
$$

筛选不向在线策略泄露未来。该条件约束模型Context，不保证多个会话在有限显存下必然全部完成。

以同构Attention缓存层、全上下文且未压缩的KV为基础，根据张量维度与真实KV头数推导每Token大小[7][8][17]：

$$
\begin{aligned}
M_{\mathrm{KV}}(B_{\mathrm{seq}},S,m)
&=B_{\mathrm{seq}}S\,2L_mH_{\mathrm{KV},m}d_{\mathrm{head},m}b_m^{\mathrm{elem}},\\
b_m^{\mathrm{KV}}&=2L_mH_{\mathrm{KV},m}d_{\mathrm{head},m}b_m^{\mathrm{elem}},\\
K_s(t)&=b_{m_s}^{\mathrm{KV}}N_s^{\mathrm{ctx}}(t).
\end{aligned}\tag{12}
$$

$B_{\mathrm{seq}}$ 为张量序列维度，单会话取1，不表示采用GPU批处理；$S$ 为缓存位置数。$L_m$ 是KV层数，$H_{\mathrm{KV},m}$ 是KV头数而非Query头数，$d_{\mathrm{head},m}$ 为头维度，$b_m^{\mathrm{elem}}$ 为元素字节数，系数2表示Key和Value。该式忽略分页碎片、额外元数据和末尾一个缓存位置的实现滞后；混合层或滑动窗口模型需另核对结构，不能直接套用同构式。

每个真实计算完成且通过容量检查的Token在同一事件提交相应KV。令 $\Delta N_s$ 为该事件新增有效Token数：

$$
N_s^{\mathrm{ctx}}(t^+)=N_s^{\mathrm{ctx}}(t^-)+\Delta N_s,
\qquad K_s(t^+)=K_s(t^-)+b_{m_s}^{\mathrm{KV}}\Delta N_s.\tag{13}
$$

普通上、下行字节分别为

$$
V_q^{\mathrm{up}}=b^{\mathrm{text}}n_q^{\mathrm{in}},\qquad
V_q^{\mathrm{down}}=b^{\mathrm{text}}n_q^{\mathrm{out}}.\tag{14}
$$

输出仅在合法提交后产生 $b^{\mathrm{text}}$ Byte，KV则用 $b_m^{\mathrm{KV}}$ 计算，两者不能混用。EOS、角色字段、协议封装和控制标识不另计Token、KV、网络Byte或GPU工作。

### 3. GPU工作量、动态等权共享与服务守恒

每台Edge设置独立的等效计算预算 $C_e^{\mathrm{GPU}}$、同时运行名额 $L_e$ 和净KV容量 $C_e^{\mathrm{KV}}$。Prefill与Decode的执行特性不同[9][10]，本文采用固定模型系数 $w_m^{\mathrm{pre}}>0$、$w_m^{\mathrm{dec}}>0$，单位为eq-work/token。已提交Token对应工作量与累计GPU服务分别定义为

$$
\begin{aligned}
W_q^{\mathrm{done}}(t)&=w_{m_s}^{\mathrm{pre}}n_q^{\mathrm{in,done}}(t)
+w_{m_s}^{\mathrm{dec}}n_q^{\mathrm{out,done}}(t),\\
W_q^{\mathrm{serv}}(t)&=W_q^{\mathrm{done}}(t)+w_q^{\mathrm{partial}}(t).
\end{aligned}\tag{15}
$$

$w_q^{\mathrm{partial}}$ 是当前未提交Token已消耗的服务量，单位为eq-work。合法提交时将该单元工作量转入 $W_q^{\mathrm{done}}$ 并清零部分量，不重置累计服务。固定每Token工作量是本文近似，不是GPU FLOPs精确计算；不声明具有文献[10]基于Profiling的预测精度。

令 $u_{q,e}(t)\in\{0,1\}$ 表示Turn实际获得节点 $e$ 的GPU服务，运行集合为 $\mathcal R_e(t)$：

$$
\begin{aligned}
\mathcal R_e(t)&=\{q:u_{q,e}(t)=1\},\quad
n_e^{\mathrm{run}}(t)=|\mathcal R_e(t)|,\\
\sum_q u_{q,e}(t)&\le L_e,\qquad
\sum_q c_{q,e}(t)\le C_e^{\mathrm{GPU}},\quad c_{q,e}(t)\ge0.
\end{aligned}\tag{16}
$$

其中 $c_{q,e}$ 为等效服务速率。独立运行数上限可参考服务框架的配置思路[20]，但其参数不直接等于本文计算预算。本文采用动态等权Processor-Sharing：

$$
c_{q,e}(t)=
\begin{cases}
C_e^{\mathrm{GPU}}/n_e^{\mathrm{run}}(t),&q\in\mathcal R_e(t),\ n_e^{\mathrm{run}}(t)>0,\\
0,&u_{q,e}(t)=0.
\end{cases}\tag{17}
$$

有空名额且有合格就绪Turn时按统一排序填充，运行集合增减后重新均分。总预算已分完并不意味着运行名额已满。文献[11][12]提供GPU共享与调度背景，官方资料[13][14]描述活跃工作负载间的计算共享与闲置份额再分配；将其抽象为精确Turn级等份是本文假设，不等同于真实硬件或同一LLM服务实例的精确执行。本文不采用Continuous Batching或批次性能曲线。

累计服务按实际速率积分，迁移中 $y_s(t)$ 可合法变化：

$$
W_q^{\mathrm{serv}}(t_2)-W_q^{\mathrm{serv}}(t_1)
=\int_{t_1}^{t_2}c_{q,y_s(t)}(t)\,\mathrm dt.\tag{18}
$$

排队、等待输入、输入交接、KVBlocked和最终冻结时服务速率为零。优先级暂停不丢失已有部分进度，未完成Token不提前计入Context、KV或响应。

### 4. 就绪队列、优先级抢占与恢复

输入已到达Execution、权威KV可用且无其他合法阻塞的Turn才具有GPU就绪资格。令 $I_q^{\mathrm{queue}}(t)$ 表示就绪但未获运行名额的指示值，$I_q^{\mathrm{compute}}(t)$ 表示实际计算指示值，则

$$
\begin{aligned}
A_q(t)&=\int_{t_q^{\mathrm{sub}}}^{t}I_q^{\mathrm{queue}}(\tau)\,\mathrm d\tau,\\
T_q^{\mathrm{queue}}&=A_q(t_q^{\mathrm{recv}}),\qquad
T_q^{\mathrm{compute}}=\int_{t_q^{\mathrm{sub}}}^{t_q^{\mathrm{recv}}}
I_q^{\mathrm{compute}}(t)\,\mathrm dt.
\end{aligned}\tag{19}
$$

$A_q$ 跨暂停和迁移保留。请求上传、输入交接等待、KVBlocked、最终STOP及仅等待下行不累加GPU就绪等待；Cutover后的合格就绪等待正常计入。等待任务按H先于L、同级 $A_q$ 降序、当前连续就绪起点升序、Turn ID升序统一排序。连续就绪起点在重新就绪时更新，但 $A_q$ 不清零；没有暂停历史的连续等待情形等价于FCFS。同刻先更新全部状态和累计量，再填充名额，避免事件枚举顺序改变排序。

高优先级Turn $q_H$ 就绪、名额已满且存在运行中低优先级Turn时，在合法计算事件边界进行一换一抢占。记低优先级候选集为 $\mathcal R_e^{\mathrm L}(t)$，以 $t_q^{\mathrm{run}}$ 表示本次进入运行集合的时刻，则唯一受害者为

$$
\begin{aligned}
q_L^*&=\underset{q\in\mathcal R_e^{\mathrm L}(t)}{\operatorname{arg\,min}_{\mathrm{lex}}}
\bigl(A_q(t),t_q^{\mathrm{run}},\operatorname{ID}(q)\bigr),\\
u_{q_L^*,e}&:1\to0,\qquad u_{q_H,e}:0\to1.
\end{aligned}\tag{20}
$$

$\operatorname{arg\,min}_{\mathrm{lex}}$ 表示按所列键依次升序比较。若全部运行Turn均为H，则不抢占同级，新H按上述统一队列等待；L不抢占H。暂停保留权威GPU KV和计算进度，恢复使用同一优先级与累计等待规则。文献[15]支持Token迭代粒度的可抢占LLM服务，文献[1]支持差异化调度背景；本文的固定H/L、受害者选择、原地保留KV及恢复排序为自定规则。

### 5. 净显存、KVBlocked与完整交付

物理显存 $M_e^{\mathrm{phys}}$ 扣除固定部署权重 $M_e^{\mathrm{weights}}$ 和运行时预留 $M_e^{\mathrm{runtime}}$ 后得到净KV预算[7][21]：

$$
\begin{aligned}
C_e^{\mathrm{KV}}&=M_e^{\mathrm{phys}}-M_e^{\mathrm{weights}}-M_e^{\mathrm{runtime}}\ge0,\\
U_e^{\mathrm{KV}}(t)&=\sum_{s\in\mathcal S(t):\,y_s(t)=e}K_s(t).
\end{aligned}\tag{21}
$$

同一Edge的模型权重只扣一次；GPU排队、暂停和生成完成仅待下行的会话仍保留权威KV。不额外设置独立会话存活人数上限。无迁移时 $U_e^{\mathrm{KV}}\le C_e^{\mathrm{KV}}$，有迁移时按D节将全部有效目标承诺计入容量。

新增KV写入前原子检查容量。不足时阻止提交并进入KVBlocked，释放运行名额，保持 $c=0$，保留合法KV、已提交Token和累计计算进度，并立即申请绕过普通冷却的安全检查。若当前单元已算完但无法提交，其服务量仍保留在 $w_q^{\mathrm{partial}}$ 中，可等于该单元完成阈值；不提前转入 $W_q^{\mathrm{done}}$ 或下行。空间恢复后只提交一次，不重复计算，保证服务守恒。尚有未提交单元的阻塞会话不具备普通迁移安全边界。

其他会话终止、迁移完成或承诺释放后重验容量；无法恢复则持续受阻，不保证所有压力事件可恢复，不临时扩容、不引入超时成功或失败。阻塞时间单独记录，不计GPU Queue或最终复制中断。该安全状态是本文规则，文献[7]仅支持有限KV容量背景。

对实际输出非空的Turn，完整交付取最后一个有效Token到达；零输出使用合法零载荷结束事件：

$$
\begin{aligned}
t_q^{\mathrm{recv}}&=
\begin{cases}
\max_{1\le h\le n_q^{\mathrm{out}}}t_{q,h}^{\mathrm{recv}},&n_q^{\mathrm{out}}>0,\\
t_q^{\mathrm{end0}},&n_q^{\mathrm{out}}=0,
\end{cases}\\
t_{q,h}^{\mathrm{recv}}&\ge t_{q,h}^{\mathrm{gen}},\qquad
D_q^{\mathrm{E2E}}=t_q^{\mathrm{recv}}-t_q^{\mathrm{sub}}.
\end{aligned}\tag{22}
$$

$t_q^{\mathrm{end0}}$ 不早于合法停止、相关输入处理及状态结算完成；在忽略控制通信的抽象下不产生额外输出Token或字节。KVBlocked未形成合法结束时不能用该事件结算完成。完整E2E覆盖上传、必要转发、就绪等待、计算、各类合法阻塞和流式交付；Decode与下行重叠，不将各阶段持续时间机械相加。

达到计划输出长度停止本轮生成；达到输出上限记OutputLengthLimit，有合法后续轮次可继续。累计Context用尽时不再提交超限KV，已生成响应完成下行并保留真实账目；若当前轮被中断或后续轮不可执行，记ContextLimit并终止，异常终止不冒充正常完成。计划最后一轮完整交付后会话自然结束，释放权威KV并安全清理无用Copy、Shadow与承诺，历史开销保留。GPU计算结束仅释放运行名额，不提前释放会话KV。观测终点尚未完成的对象保留未完成状态。

## D. Joint Session Re-placement Model

### 1. 联合检查与目标布局

第 $j$ 次实际联合检查发生于 $t_j$，面向全部 $\mathcal S(t_j)$。有效移动、当前Turn首次SLA预警、实际KV压力及低频周期构成四类触发。统一SLA门槛为 $D^{\max}$、预警比例为 $0<\theta<1$：

$$
t_q^{\mathrm{warn}}=t_q^{\mathrm{sub}}+\theta D^{\max}.\tag{23}
$$

到该时刻尚未完整交付才申请一次预警检查，首次申请即置位，延期不重复触发。普通检查受冷却 $\delta_{\mathrm{cool}}$ 和周期 $\Delta_{\mathrm{check}}$ 协调；同刻触发合并，冷却内仅保留一个普通待办并记录原因，冷却结束按当前状态重验，执行一次或清除过期申请。真实KV压力先保护写入，立即安全检查，可吸收同刻普通待办，不受冷却延迟。高优先级到达先由GPU规则处理，初始到达不直接全域调整。上述触发、合并和冷却为本文规则，文献[1]提供运行期重调度背景。

对存活会话选择目标二元布局 $z_{s,e,j}$，$z=1$ 表示计划将会话安排至 $e$：

$$
\sum_{e\in\mathcal E}z_{s,e,j}=1,\quad
z_{s,e,j}\le x_{e,m_s},\quad z_{s,e,j}\in\{0,1\},
\qquad x_{y_s(t),m_s}=1.\tag{24}
$$

前三项作用于 $s\in\mathcal S(t_j)$ 和候选Edge，最后一项作用于存活期实际节点。一次可No-op、调整一个或多个会话，静止用户同样可参与。$z$ 为目标意图，不等于实际权威位置 $y_s$；未完成安全Cutover时实际位置不变。最终布局容量可行不代表过程可执行，每项Copy和扩容必须检查当时真实资源，不能预支其他会话尚未释放的源端空间；两个满载节点也不能以瞬时交换跳过迁移承诺。

### 2. 迁移操作、Shadow与容量承诺

每次启动迁移生成唯一ID $\mu$，属性包括 $s(\mu)$、$e_{\mathrm{src}}(\mu)$、$e_{\mathrm{dst}}(\mu)$ 及 $t_\mu^{\mathrm{start}}$。以 $\mathcal I^{\mathrm{act}}(t)$ 表示尚未清理的有效迁移操作集，$\mathcal I^{\mathrm{hist}}$ 表示运行中曾启动的全部操作集；前者用于当前容量，后者用于历史成本。会话—源—目标属性相同不代表ID相同，取消后重启使用新ID并保留旧账目。

对有效迁移定义一致前缀 $X_\mu(t)$、实际物化Shadow $H_\mu(t)$ 和含Shadow的总容量承诺 $Q_\mu(t)$，均为Byte：

$$
\begin{aligned}
0&\le X_\mu(t)\le H_\mu(t)\le Q_\mu(t),\quad\mu\in\mathcal I^{\mathrm{act}}(t),\\
U_e^{\mathrm{KV}}(t)&+
\sum_{\substack{\mu\in\mathcal I^{\mathrm{act}}(t):\\e_{\mathrm{dst}}(\mu)=e}}Q_\mu(t)
\le C_e^{\mathrm{KV}},\quad e\in\mathcal E.
\end{aligned}\tag{25}
$$

忽略分页、重复报文和额外中间缓存时取 $H_\mu=X_\mu$。$Q$ 已含 $H$，不能再加一次；未物化承诺限制可用容量但不等于物化驻留。源端在Cutover前继续占权威KV。文献[1]描述逐阶段目标预分配与失败清理，文献[16]描述Reservation和最终提交；上述精确容量拆账是本文定义。

复制启动前须原子承诺当前已有完整KV：

$$
Q_\mu(t_\mu^{\mathrm{start}})\ge K_{s(\mu)}(t_\mu^{\mathrm{start}}).\tag{26}
$$

只在源端真实生成新增KV后按需扩容，不提前预留未来整个输出。目标扩容失败可延后或安全取消普通复制，源端自身容量不足则按KVBlocked处理；两者都不能先改权威位置或越界写入。

### 3. 在线Pre-copy与安全冻结

采用Llumnix的追加式KV在线同步机制[1]及经典Pre-copy阶段思想[16]。Prepare检查模型、路径、冲突与容量；Initial Live Copy复制启动时已有完整前缀，同时允许源端继续计算；Incremental Live Copy追赶实际新增KV；只有初始复制完成且满足安全条件后，才Stop-and-Copy冻结并同步最后尾部，继而Atomic Cutover。源端“允许计算”仍须满足GPU就绪和资源条件，不代表必然生成Token。本文不采用VM脏页重传，既有不可变KV前缀不重复复制。

$$
\begin{aligned}
K_\mu^0&=K_{s(\mu)}(t_\mu^{\mathrm{start}}),\\
Z_\mu(t)&=K_{s(\mu)}(t)-X_\mu(t)\ge0,\\
\Delta Z_\mu&=\Delta K_{s(\mu)}-\Delta X_\mu.
\end{aligned}\tag{27}
$$

$X_\mu\ge K_\mu^0$ 标记InitialDone。网络任务 $f_\mu$ 的实际有线速率须转换为Byte/s：

$$
\begin{aligned}
v_\mu^{\mathrm{copy}}(t)&=r_{f_\mu}(t)/8,\\
g_s^{\mathrm{KV}}(t)&=b_{m_s}^{\mathrm{KV}}r_s^{\mathrm{token}}(t),\\
\frac{\mathrm dZ_\mu}{\mathrm dt}&=g_{s(\mu)}^{\mathrm{KV}}-v_\mu^{\mathrm{copy}}.
\end{aligned}\tag{28}
$$

$r_s^{\mathrm{token}}$ 为真实Token提交速率的连续近似，导数式仅在有待复制字节、采用流体近似时解释趋势；事件级增量守恒为主规则，不能在空队列处把尾部推成负数，也不假定复制必然快于生成。

令 $\widehat v_\mu^{\mathrm{copy}}$ 为STOP前依据当前网络状态取得的复制速率估计，$\mathrm{SafeBoundary}_\mu$ 表示合法输入和计算边界，$\mathrm{CapacityOK}_\mu$ 表示模型、路径及目标承诺仍合法。普通主动迁移进入STOP必须满足

$$
\begin{aligned}
\mathrm{InitialDone}_\mu(t)\ &\land\ \mathrm{SafeBoundary}_\mu(t)
\ \land\ \mathrm{CapacityOK}_\mu(t)\\
&\land\left[Z_\mu(t)=0\ \lor\left(
\widehat v_\mu^{\mathrm{copy}}(t)>0\ \land\
\frac{Z_\mu(t)}{\widehat v_\mu^{\mathrm{copy}}(t)}\le I_{\max}^{\mathrm{mig}}
\right)\right].
\end{aligned}\tag{29}
$$

零尾部不要求正速率。准入是本文根据Byte/速率建立的事前门槛，不能解释为实际冻结时长的硬保证。Initial未完成时不允许提前停止源端等待完整复制；准入未满足时继续后台追赶、延后或安全取消，不引入额外带宽控制或压制Token生成的动作。

安全边界按当前阶段确定：请求仍在UE上传或Access→Source途中时不STOP；正在Prefill则先在Source完成本轮Prefill；Decode仅在当前Token/KV完整提交且 $w_q^{\mathrm{partial}}=0$ 时冻结；生成完毕仅待下行也可切换。输入已到Source但尚未Prefill的排队Turn，先沿Source→Target真实转发 $b^{\mathrm{text}}n_q^{\mathrm{in}}$ Byte。输入交接期间Source不启动Prefill，完成后重验准入，可无需取得源端GPU即冻结；此等待计E2E，不计GPU Queue或最终冻结。交接字节参与有线竞争并单独报告，不是免费元数据或KV复制。输入及阶段不变时可复用已交接副本；取消则目标副本失效，已发生字节保留。

冻结源端后定义

$$
K_\mu^{\mathrm{stop}}=K_{s(\mu)}(t_\mu^{\mathrm{stop}}),\qquad
Z_\mu^{\mathrm{tail}}=K_\mu^{\mathrm{stop}}-X_\mu(t_\mu^{\mathrm{stop}}).\tag{30}
$$

冻结期间源端不新增KV，只同步固定尾部。真实容量压力仍先阻止非法写入并检查安全恢复，不因迁移未完成允许超额写入，也不保证带有未提交计算单元的阻塞会话能立即迁移。

### 4. 原子Cutover、取消与跨检查协调

仅对成功切换，目标收到完整冻结状态且完成必要状态接续后才发生Cutover：

$$
X_\mu(t_\mu^{\mathrm{cut}})=K_\mu^{\mathrm{stop}},\qquad
I_\mu^{\mathrm{mig}}=t_\mu^{\mathrm{cut}}-t_\mu^{\mathrm{stop}},\qquad
y_{s(\mu)}((t_\mu^{\mathrm{cut}})^+)=e_{\mathrm{dst}}(\mu).\tag{31}
$$

同步等式在原子提交前检查，提交后将Shadow转为目标权威KV、清除该操作承诺并释放旧源KV，避免双重计数。进入STOP即撤销源端计算资格；切换还需交接会话和Turn标识、固定模型/优先级、Prefill/Decode阶段、Token计数、Context、已提交和累计服务、累计等待、队列归属与输出交付进度。只有目标仍需计算且输入可用时才建立GPU就绪资格，仅待下行者不创建计算任务。任何时刻都不允许两个节点同时推进同一Turn。

旧路径上已生成响应保留进度，新Token从新权威节点发送并遵守FIFO。若STOP跨越上一轮完整交付边界，下一轮仍按原时刻提交、更新Access并保留时间戳，但实际请求上传延期至Cutover或失败解冻，再发向届时唯一权威节点；延期计新轮E2E，不计GPU Queue，不虚构发往旧源的在途输入，也不破坏冻结KV。

冻结后网络变化可能使实际 $I_\mu^{\mathrm{mig}}$ 超过预计预算，须照实记录，不能截断。Cutover后GPU就绪等待计Queue和E2E，不计冻结复制中断。切换前取消或失败时Source仍唯一权威，安全恢复并释放目标Shadow/承诺；若实际进入STOP，失败中断为

$$
I_\mu^{\mathrm{mig,fail}}=t_\mu^{\mathrm{resume}}-t_\mu^{\mathrm{stop}},
\qquad N_s^{\mathrm{stop}}\le M_{\max}^{\mathrm{mig}}.\tag{32}
$$

$t_\mu^{\mathrm{resume}}$ 为源端安全解冻时刻。成功Cutover式不应用于取消或失败操作。$N_s^{\mathrm{stop}}$ 为普通主动迁移实际进入STOP的累计次数，失败亦计次，仅后台复制不计次；次数限制是本文防频繁冻结规则，不是迁移Byte预算。紧急物理安全恢复依其合法边界执行，不获得越界或强制恢复许可。

后台复制可跨越多个Turn和Check。新目标等于既有Target时复用原ID、前缀、Shadow与承诺；冲突时保持原Copy、延后新意图，或在Cutover前安全取消后新建操作。无在途Copy且目标等于实际节点为No-op。不同会话可并行复制并共享网络和容量；同一会话不得向冲突目标并行复制，不完整Shadow不得独立推理。会话自然结束时清理无用操作，既有成本不清零。这些协调规则借鉴文献[1]的阶段协调和异常清理思想，具体跨Turn、跨Check语义由本文定义。

## E. Problem Formulation

### 1. 在线决策与实际性能指标

令 $\mathcal O_j$ 为第 $j$ 次检查时可用的当前和历史信息，包括Access、实际权威节点、计算/队列进度、KV与有效承诺、在途迁移及当前网络状态。在线策略 $\pi$ 只选择目标布局：

$$
\boldsymbol z_j=\pi(\mathcal O_j),\qquad \pi\in\Pi_{\mathrm{causal}}.\tag{33}
$$

模型部署、路径、GPU共享和优先级规则、有线Max-Min及迁移安全执行器固定，不是额外决策动作。未来工作负载、尚未生成的输出及未来移动不属于 $\mathcal O_j$。

令 $\omega$ 为预生成有限负载实例，$\mathcal Q^{\mathrm{all}}(\omega)$ 为按照C节合法长度规则构造的全部计划Turn集合：

$$
N_{\mathrm{turn}}(\omega)=|\mathcal Q^{\mathrm{all}}(\omega)|>0.\tag{34}
$$

所有算法复用同一 $\omega$ 和全量分母，Turn真实提交时刻可以随策略不同而不同。仅当该负载全部计划合法Turn均有真实完整交付时刻时，平均时延定义为

$$
\overline D^{\mathrm{E2E}}(\pi;\omega)=
\frac{\displaystyle\sum_{q\in\mathcal Q^{\mathrm{all}}(\omega)}D_q^{\mathrm{E2E}}(\pi;\omega)}
{N_{\mathrm{turn}}(\omega)}.\tag{35}
$$

式(35)使用式(22)的完整响应事件，不以TTFT、纯GPU时间或完成者子集替代。高低优先级在主指标中按Turn等权。

迁移成本按唯一操作ID记账。令 $V_\mu^{\mathrm{actual}}(T_{\mathrm{obs}})$ 为截至观测终点实际传输的逻辑KV Byte，非有效期的 $H_\mu(t)$ 记为零，则

$$
\begin{aligned}
V^{\mathrm{mig}}(\pi;\omega)&=\sum_{\mu\in\mathcal I^{\mathrm{hist}}}
V_\mu^{\mathrm{actual}}(T_{\mathrm{obs}}),\\
A^{\mathrm{shadow}}(\pi;\omega)&=\int_0^{T_{\mathrm{obs}}}
\sum_{\mu\in\mathcal I^{\mathrm{hist}}}H_\mu(t)\,\mathrm dt.
\end{aligned}\tag{36}
$$

两者单位为Byte和Byte·s，取消、失败及重启前已发生开销均保留，不按网络跳数重复计数；$Q_\mu-H_\mu$ 不计物化驻留。普通业务及输入交接字节单独统计，不计KV复制。冻结次数及真实中断另行报告，其对Turn的影响已包含在E2E中，不重复相加。可进一步报告归一化值

$$
\overline V^{\mathrm{mig}}=V^{\mathrm{mig}}/N_{\mathrm{turn}},\qquad
\overline A^{\mathrm{shadow}}=A^{\mathrm{shadow}}/N_{\mathrm{turn}}.\tag{37}
$$

它们仅是统计量，不构成预算或目标项。不同运行采用一致观察或完整Drain口径，并同时报告完成度。

### 2. 主要优化目标及完成性边界

以 $\Pi_{\mathrm{causal,safe}}$ 表示仅使用因果信息、所有实际操作符合B–D节容量及状态安全规则的在线策略集合。在全量交付指标有定义且其期望可计算的评价范围内，本文的主要目标为

$$
\min_{\pi\in\Pi_{\mathrm{causal,safe}}}
\mathbb E_{\omega}\!\left[\overline D^{\mathrm{E2E}}(\pi;\omega)\right].\tag{38}
$$

该式用于表达可完整交付工作负载上的时延优化，不赋高低优先级不同权重，不设置KV Byte或Shadow Byte·s硬预算，也不与秒量纲直接加权。式(36)–(37)记录成本，不意味着式(38)已数学限制迁移频率，不能据此保证低迁移开销。

安全可行并不保证完成：长期KVBlocked、观测截尾或异常终止可能使部分计划Turn没有完整交付时刻。此时全量均值标记为不可计算，主目标的期望也不能按未定义样本求值；不得赋零时延、伪造时间或以完成者均值冒充全量均值。本文不额外设定无穷损失、失败罚分或硬超时，因此该目标尚不对长期不完成的所有安全策略提供统一数值排序；不能删去对某算法不利的未完成样本来制造可比均值。

令 $N_{\mathrm{sub}}$ 为截至观察终点真实提交数、$N_{\mathrm{done}}$ 为正常完整交付数，采用

$$
\begin{aligned}
N_{\mathrm{unfinished}}&=N_{\mathrm{turn}}-N_{\mathrm{done}},\qquad
\rho_{\mathrm{done}}=N_{\mathrm{done}}/N_{\mathrm{turn}},\\
N_{\mathrm{unfinished}}&=(N_{\mathrm{sub}}-N_{\mathrm{done}})
+(N_{\mathrm{turn}}-N_{\mathrm{sub}}).
\end{aligned}\tag{39}
$$

前一部分还须区分已提交仍等待、长期阻塞和异常终止，后一部分为尚未提交的后续轮次。对已提交未完成且仍在观察中的Turn，仅报告 $T_{\mathrm{obs}}-t_q^{\mathrm{sub}}$ 作为截至终点的右删失时延下界；未提交者不虚构提交时刻。KVBlocked另报次数、时长、受影响比例和恢复率，异常结束单独标记，不强制解释为正常交付。

SLA保留统一阈值和预警触发，但不进入主目标或硬可行性约束。对于全量已正常交付的优先级组，定义

$$
v_q^{\mathrm{SLA}}=\mathbf1\{D_q^{\mathrm{E2E}}>D^{\max}\},\qquad
\rho_p^{\mathrm{SLA}}=
\frac{\sum_{q\in\mathcal Q_p^{\mathrm{all}}}v_q^{\mathrm{SLA}}}
{|\mathcal Q_p^{\mathrm{all}}|},\quad p\in\{\mathrm H,\mathrm L\}.\tag{40}
$$

$\mathcal Q_p^{\mathrm{all}}$ 为固定优先级组的计划合法Turn集合，分母非零且该组全部完成才报告完整违约率；否则报告缺失和未完成状态。预警不是实际违约。若实验关闭预警检查，须作为独立实验配置说明，不能视为完整环境未改变。

### 3. 可行性约束汇总

在线布局及其执行共同受前述规则约束：式(24)约束目标和模型兼容，式(16)–(18)约束GPU名额、份额与进度，式(2)–(4)约束有线容量与字节推进，式(9)–(13)约束Context及KV增长，式(25)–(32)约束在途容量、准备、冻结与切换。目标层满足唯一指派与模型兼容；实际服务层满足单会话串行与唯一权威；计算和网络层分别满足名额、预算及Max-Min；存储与迁移层满足净容量、启动承诺、真实Token提交、初始复制、必要STOP准入和一致Cutover。特别地，GPU计算只能在当前权威节点推进：

$$
u_{q,e}(t)=1\ \Longrightarrow\ e=y_s(t),\qquad
\sum_{e\in\mathcal E}u_{q,e}(t)\le1,\quad q=(s,k).\tag{41}
$$

上述是唯一权威与计算资格的数学表达，不开放第二执行端。GPU等权份额、网络公平和迁移进度由固定环境更新，并非新增优化变量。所有容量条件作用于每个事件前后的真实中间状态；目标布局可行不能跳过源端保留和目标预留，也不能保证无合法恢复路径的会话最终完成。


## References

[1] Sun B, Huang Z, Zhao H, et al. Llumnix: Dynamic Scheduling for Large Language Model Serving[C]//18th USENIX Symposium on Operating Systems Design and Implementation. 2024: 173–191. [来源](https://www.usenix.org/conference/osdi24/presentation/sun-biao)。

[2] Wang S, Urgaonkar R, Zafer M, et al. Dynamic Service Migration in Mobile Edge Computing Based on Markov Decision Process[J]. IEEE/ACM Transactions on Networking, 2019. DOI: 10.1109/TNET.2019.2916577. [来源](https://research.ibm.com/publications/dynamic-service-migration-in-mobile-edge-computing-based-on-markov-decision-process)。

[3] Floyd S, ed. Metrics for the Evaluation of Congestion Control Mechanisms[R]. RFC 5166, 2008, §2.3.2. DOI: 10.17487/RFC5166. [来源](https://www.rfc-editor.org/rfc/rfc5166.html)。

[4] Gu X, Ji C, Zhang G. Energy-Optimal Latency-Constrained Application Offloading in Mobile-Edge Computing[J]. Sensors, 2020, 20(11): 3064. DOI: 10.3390/s20113064. [来源](https://pmc.ncbi.nlm.nih.gov/articles/PMC7309048/)。

[5] Yu L, Lin J, Li J. Stateful Large Language Model Serving with Pensieve[C]//Proceedings of the Twentieth European Conference on Computer Systems. 2025. DOI: 10.1145/3689031.3696086. [来源](https://doi.org/10.1145/3689031.3696086)。

[6] Gao B, He Z, Sharma P, et al. Cost-Efficient Large Language Model Serving for Multi-turn Conversations with CachedAttention[C]//USENIX Annual Technical Conference. 2024: 111–126. [来源](https://www.usenix.org/conference/atc24/presentation/gao-bin-cost)。

[7] Kwon W, Li Z, Zhuang S, et al. Efficient Memory Management for Large Language Model Serving with PagedAttention[C]//29th Symposium on Operating Systems Principles. 2023. DOI: 10.1145/3600006.3613165. [来源](https://arxiv.org/abs/2309.06180)。

[8] Ainslie J, Lee-Thorp J, de Jong M, et al. GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints[C]//EMNLP. 2023: 4895–4901. DOI: 10.18653/v1/2023.emnlp-main.298. [来源](https://aclanthology.org/2023.emnlp-main.298/)。

[9] Yu G I, Jeong J S, Kim G W, et al. Orca: A Distributed Serving System for Transformer-Based Generative Models[C]//16th USENIX Symposium on Operating Systems Design and Implementation. 2022: 521–538. [来源](https://www.usenix.org/conference/osdi22/presentation/yu)。

[10] Agrawal A, Kedia N, Mohan J, et al. Vidur: A Large-Scale Simulation Framework for LLM Inference[C]//Proceedings of Machine Learning and Systems. 2024, 6. [来源](https://proceedings.mlsys.org/paper_files/paper/2024/hash/b74a8de47d2b3c928360e0a011f48351-Abstract-Conference.html)。

[11] Yu P, Chowdhury M. Fine-Grained GPU Sharing Primitives for Deep Learning Applications[C]//Proceedings of Machine Learning and Systems. 2020, 2. [来源](https://proceedings.mlsys.org/paper_files/paper/2020/hash/d9cd83bc91b8c36a0c7c0fcca59228f2-Abstract.html)。

[12] Xiao W, Bhardwaj R, Ramjee R, et al. Gandiva: Introspective Cluster Scheduling for Deep Learning[C]//13th USENIX Symposium on Operating Systems Design and Implementation. 2018: 595–610. [来源](https://www.usenix.org/conference/osdi18/presentation/xiao)。

[13] Karabulut E, Lifshitz D, Sharon H. Memory-Enforced GPU Sharing in Kubernetes with NVIDIA CUDA 13.4[EB/OL]. NVIDIA Technical Blog, 2026-10-27 [2026-11-03]. [来源](https://developer.nvidia.com/blog/memory-enforced-gpu-sharing-in-kubernetes-with-nvidia-cuda-13-4/)。

[14] NVIDIA. GPU Compute Modes: Run:ai Self-Hosted v3.0[EB/OL]. [2026-11-03]. [来源](https://docs.nvidia.com/run-ai/self-hosted/v3.0/documentation/platform-management/runai-scheduler/resource-optimization/gpu-fractions/compute-modes)。

[15] Wu B, Zhong Y, Zhang Z, et al. FastServe: Iteration-Level Preemptive Scheduling for Large Language Model Inference[C]//23rd USENIX Symposium on Networked Systems Design and Implementation. 2026: 57–74. [来源](https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang)。

[16] Clark C, Fraser K, Hand S, et al. Live Migration of Virtual Machines[C]//2nd Symposium on Networked Systems Design and Implementation. 2005. [来源](https://www.usenix.org/legacy/publications/library/proceedings/nsdi05/tech/full_papers/clark/clark_html/index.html)。

[17] Hugging Face. Transformers v4.57.0: Caching[EB/OL]. [2026-11-03]. [来源](https://huggingface.co/docs/transformers/v4.57.0/cache_explanation)。

[18] vLLM. Model Configuration[EB/OL]. [2026-11-03]. [来源](https://docs.vllm.ai/en/latest/api/vllm/config/model/)。

[19] vLLM. Sampling Parameters[EB/OL]. [2026-11-03]. [来源](https://docs.vllm.ai/en/stable/api/vllm/sampling_params/)。

[20] vLLM. Scheduler Configuration[EB/OL]. [2026-11-03]. [来源](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/)。

[21] vLLM. Cache Configuration[EB/OL]. [2026-11-03]. [来源](https://docs.vllm.ai/en/latest/api/vllm/config/cache/)。
