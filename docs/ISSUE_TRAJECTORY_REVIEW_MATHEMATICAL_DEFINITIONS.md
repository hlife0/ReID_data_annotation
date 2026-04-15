# 轨迹级 Review 数学定义（公理化版本）

本文档仅给出一组**数学定义**，用于统一后续设计、实现与讨论中的术语。

本文档**不**讨论以下内容：

- 不讨论 UI
- 不讨论人工操作流程
- 不讨论具体算法
- 不讨论数据库结构
- 不讨论导出格式
- 不讨论实现细节

本文档只讨论：

- 集合
- 函数
- 关系
- 区间
- 稳定段
- $issue$
- 身份映射
- 帧级结果

---

## 1. 记号约定

### 1.1 基本数集

记：

- $\mathbb{N} = \{1, 2, 3, \dots\}$
- $\mathbb{R}_{\ge 0} = \{x \in \mathbb{R} : x \ge 0\}$

### 1.2 区间

若 $m, n \in \mathbb{N}$ 且 $m \le n$，记离散整数区间

$$
[m, n] := \{ t \in \mathbb{N} : m \le t \le n \}.
$$

称 $I \subseteq \mathbb{N}$ 为一个离散区间，当且仅当存在 $m,n$ 使得 $I=[m,n]$。

### 1.3 极大性

若某性质 $\mathcal{P}$ 定义在区间上，则称区间 $I$ 是一个**极大 $\mathcal{P}$ 区间**，当且仅当：

1. $I$ 满足性质 $\mathcal{P}$
2. 不存在严格更大的区间 $J \supsetneq I$ 仍满足 $\mathcal{P}$

---

## 2. 原始对象

### 2.1 Session

一个 $session$ 记作 $\Sigma$。

其帧指标集合记作

$$
F_{\Sigma} = [1, T_{\Sigma}]
$$

其中 $T_{\Sigma} \in \mathbb{N}$ 为该 $session$ 的总帧数。

### 2.2 人物槽位集合

定义固定人物槽位集合

$$
P := \{p_1, p_2, \dots, p_7\}.
$$

这里的 $p_i$ 表示固定真人身份槽位，而不是临时编辑槽位。

### 2.3 AI 轨迹标识集合

对每个 $session \Sigma$，定义其 AI 轨迹标识全集

$$
K_{\Sigma}
$$

为该 $session$ 中所有 AI $track\_id$ 的有限集合。

### 2.4 边框空间

定义边框空间

$$
\mathcal{B} := \mathbb{R}_{\ge 0}^4.
$$

若 $b=(x,y,w,h)\in\mathcal{B}$，则解释为：

- $x$：bbox 左上角横坐标
- $y$：bbox 左上角纵坐标
- $w$：bbox 宽
- $h$：bbox 高

### 2.5 帧级可见轨迹集合

对每个 $t \in F_{\Sigma}$，定义该帧中 AI 可见轨迹集合

$$
A_{\Sigma}(t) \subseteq K_{\Sigma}.
$$

直观上，$A_{\Sigma}(t)$ 表示第 $t$ 帧中 AI 认为“存在有效框”的所有轨迹标识集合。

### 2.6 帧级边框函数

对每个 $t \in F_{\Sigma}$，定义

$$
b_{\Sigma,t} : A_{\Sigma}(t) \to \mathcal{B}
$$

其中 $b_{\Sigma,t}(k)$ 表示第 $t$ 帧中轨迹 $k$ 的边框。

### 2.7 帧级重叠函数

对每个 $t \in F_{\Sigma}$，定义

$$
\mathrm{ov}_{\Sigma,t} : A_{\Sigma}(t)\times A_{\Sigma}(t)\to [0,1].
$$

其中 $\mathrm{ov}_{\Sigma,t}(k_1,k_2)$ 表示第 $t$ 帧中轨迹 $k_1$ 与 $k_2$ 的重叠度。

本文档不规定其具体计算公式，只要求其值域位于 $[0,1]$。

---

## 3. 派生对象

### 3.1 轨迹存在区间

对任意 $k \in K_{\Sigma}$，定义其存在帧集合

$$
E_{\Sigma}(k) := \{ t \in F_{\Sigma} : k \in A_{\Sigma}(t)\}.
$$

### 3.2 帧级轨迹数

定义帧级轨迹数函数

$$
c_{\Sigma}(t) := |A_{\Sigma}(t)|.
$$

### 3.3 区间上的恒定轨迹集合

若区间 $I \subseteq F_{\Sigma}$ 满足：

$$
\forall s,t\in I,\quad A_{\Sigma}(s)=A_{\Sigma}(t),
$$

则称 $I$ 上轨迹集合恒定，并记该恒定集合为

$$
K_{\Sigma}(I) := A_{\Sigma}(t), \quad t\in I.
$$

此定义良定，因为在该条件下 $A_{\Sigma}(t)$ 与所选 $t$ 无关。

---

## 4. 参数

本文档引入一个抽象重叠阈值

$$
\tau_{\mathrm{ov}} \in [0,1].
$$

本文档不规定其具体数值；任何后续系统都可选定具体常数。

---

## 5. 稳定区间与稳定段

### 5.1 稳定区间

设 $I=[m,n]\subseteq F_{\Sigma}$ 为非空离散区间。

称 $I$ 为 $session \Sigma$ 的一个**稳定区间**，当且仅当以下条件同时成立：

1. 轨迹集合在 $I$ 上恒定，即

$$
\forall s,t\in I,\quad A_{\Sigma}(s)=A_{\Sigma}(t).
$$

2. 在 $I$ 上不存在超过阈值的轨迹间重叠，即

$$
\forall t\in I,\ \forall k_1,k_2\in A_{\Sigma}(t),\ k_1\ne k_2
\Longrightarrow
\mathrm{ov}_{\Sigma,t}(k_1,k_2)\le \tau_{\mathrm{ov}}.
$$

条件 1 已经蕴含：

- $I$ 内无新增轨迹
- $I$ 内无消失轨迹
- $I$ 内无入镜
- $I$ 内无出镜

因此不再单独重复书写这些条件。

### 5.2 稳定段

称区间 $S \subseteq F_{\Sigma}$ 为 $session \Sigma$ 的一个**稳定段**，当且仅当：

- $S$ 是一个极大稳定区间

即 $S$ 满足稳定区间定义，且不能被真包含于更大的稳定区间中。

### 5.3 稳定段族

记 $\Sigma$ 上所有稳定段的集合为

$$
\mathcal{S}_{\Sigma}.
$$

定义稳定帧集合

$$
\mathrm{Stab}_{\Sigma}
:=
\bigcup_{S\in\mathcal{S}_{\Sigma}} S.
$$

---

## 6. Issue

### 6.1 issue 帧集合

定义 $session \Sigma$ 的 issue 帧集合为稳定帧集合在 $F_{\Sigma}$ 中的补：

$$
\mathrm{Iss}_{\Sigma}
:=
F_{\Sigma}\setminus \mathrm{Stab}_{\Sigma}.
$$

### 6.2 issue 区间

称非空区间 $I\subseteq F_{\Sigma}$ 为 $session \Sigma$ 的一个 **issue 区间**，当且仅当：

1. $I \subseteq \mathrm{Iss}_{\Sigma}$
2. $I$ 是 $\mathrm{Iss}_{\Sigma}$ 中的极大离散区间

换言之，issue 区间就是 issue 帧集合的极大连续分量。

### 6.3 issue 族

记 $\Sigma$ 上所有 issue 区间的集合为

$$
\mathcal{I}_{\Sigma}.
$$

---

## 7. 稳定段与 issue 的分解

### 命题 7.1

对任一 $session \Sigma$，

$$
F_{\Sigma}
=
\mathrm{Stab}_{\Sigma}
\sqcup
\mathrm{Iss}_{\Sigma},
$$

其中 $\sqcup$ 表示不交并。

### 命题 7.2

集合族 $\mathcal{S}_{\Sigma}\cup \mathcal{I}_{\Sigma}$ 构成 $F_{\Sigma}$ 的一个不交区间分解。

即：

1. 每个元素都是 $F_{\Sigma}$ 的非空离散区间
2. 任意两个不同元素不相交
3. 它们的并为 $F_{\Sigma}$

### 命题 7.3

若 $S=[m,n]\in\mathcal{S}_{\Sigma}$ 且 $m>1$，则存在唯一的区间 $I\in\mathcal{I}_{\Sigma}$ 满足：

$$
\max I = m-1
$$

或存在唯一的区间 $S' \in \mathcal{S}_{\Sigma}$ 满足：

$$
\max S' = m-1.
$$

即任一非首稳定段左侧，紧邻它的要么是一个 issue 区间，要么是另一个稳定段；不存在空洞。

同理，若 $S=[m,n]\in\mathcal{S}_{\Sigma}$ 且 $n<T_{\Sigma}$，则其右侧也存在唯一紧邻区间。

---

## 8. 稳定段上的身份映射

### 8.1 可见轨迹集合

若 $S\in\mathcal{S}_{\Sigma}$，则其轨迹集合恒定。记

$$
K_{\Sigma}(S)
$$

为该稳定段的可见轨迹集合。

### 8.2 段级身份映射

对任一稳定段 $S\in\mathcal{S}_{\Sigma}$，定义其**段级身份映射**为一个单射

$$
\phi_S : K_{\Sigma}(S)\to P.
$$

这里“单射”表示：

$$
\forall k_1,k_2\in K_{\Sigma}(S),\ 
\phi_S(k_1)=\phi_S(k_2)\Longrightarrow k_1=k_2.
$$

其含义是：

- 在同一稳定段中，不同可见轨迹不能对应到同一个固定人物槽位

但 $\phi_S$ 不要求是满射，因为：

- 一个稳定段中不一定七个人都同时可见

### 8.3 稳定段身份化

若某稳定段 $S$ 配备了段级身份映射 $\phi_S$，则称 $S$ 已被**身份化**。

---

## 9. 帧级结果空间

### 9.1 结果状态空间

定义结果状态集合

$$
\mathcal{Q}
:=
\{\mathrm{absent},\mathrm{occluded},\mathrm{outside}\}
\cup
\bigl(\{\mathrm{visible}\}\times \mathcal{B}\bigr).
$$

元素解释如下：

- $\mathrm{absent}$：该人物在该帧结果中不存在
- $\mathrm{occluded}$：该人物在该帧结果中被遮挡
- $\mathrm{outside}$：该人物在该帧结果中位于画面外
- $(\mathrm{visible},b)$：该人物在该帧结果中可见，且边框为 $b$

### 9.2 帧级最终结果

定义 $session \Sigma$ 的**帧级最终结果**为函数

$$
R_{\Sigma} : F_{\Sigma}\times P \to \mathcal{Q}.
$$

对任意帧 $t$ 和任意固定人物槽位 $p\in P$，

$$
R_{\Sigma}(t,p)
$$

表示该帧上人物 $p$ 的结果状态。

---

## 10. 由稳定段身份映射诱导的帧级结果

设 $S\in\mathcal{S}_{\Sigma}$ 且 $S$ 已身份化，其身份映射为

$$
\phi_S : K_{\Sigma}(S)\to P.
$$

则对任意 $t\in S$，可定义由 $\phi_S$ 诱导的局部帧级结果

$$
R_{\Sigma}^S(t,\cdot): P\to\mathcal{Q}
$$

如下：

1. 若存在 $k\in K_{\Sigma}(S)$ 使得 $\phi_S(k)=p$，则

$$
R_{\Sigma}^S(t,p)
=
(\mathrm{visible}, b_{\Sigma,t}(k)).
$$

2. 若不存在 $k\in K_{\Sigma}(S)$ 满足 $\phi_S(k)=p$，则

$$
R_{\Sigma}^S(t,p)=\mathrm{absent}.
$$

由于稳定段中 $K_{\Sigma}(S)$ 在每一帧恒定，因此上述定义良定。

---

## 11. 第一稳定帧

若 $S=[m,n]\in\mathcal{S}_{\Sigma}$，称 $m$ 为 $S$ 的**第一稳定帧**，称 $n$ 为 $S$ 的**最后稳定帧**。

由于 $S$ 上轨迹集合恒定，因此：

$$
A_{\Sigma}(m)=A_{\Sigma}(t),\quad \forall t\in S.
$$

于是，对稳定段而言，只要 $m$ 上的轨迹集合被赋予段级身份映射 $\phi_S$，则该映射已定义了 $S$ 上每一帧的可见身份结构。

---

## 12. 关键命题

### 命题 12.1

设 $S=[m,n]\in\mathcal{S}_{\Sigma}$。

若给定一个单射

$$
\phi_S:K_{\Sigma}(S)\to P,
$$

则 $S$ 上由 $\phi_S$ 诱导的局部帧级结果

$$
R_{\Sigma}^S(t,\cdot),\quad t\in S
$$

唯一确定。

### 命题 12.2

稳定段内部不需要额外的轨迹出生/消失信息，因为：

$$
\forall s,t\in S,\quad A_{\Sigma}(s)=A_{\Sigma}(t).
$$

因此稳定段的全部身份结构，完全由：

1. 稳定段本身 $S$
2. 其恒定轨迹集合 $K_{\Sigma}(S)$
3. 其段级身份映射 $\phi_S$

三者决定。

### 命题 12.3

若 $S=[m,n]\in\mathcal{S}_{\Sigma}$，则 $m$ 之前的所有不稳定性均不属于 $S$ 的定义内容。

也就是说，$S$ 的稳定性仅依赖于区间内部的性质，而不依赖于 $m-1$ 帧是否与 $m$ 具有相同的轨迹集合。

因此：

- 稳定段的左邻域可以是 $issue$ 区间
- 也可以是另一个稳定段
- 但这不会改变 $S$ 作为稳定段的定义

---

## 13. 全局目标的纯数学形式

对一个给定 $session \Sigma$，轨迹级 review 的纯数学目标可表述为：

1. 求出稳定段族 $\mathcal{S}_{\Sigma}$
2. 求出 issue 族 $\mathcal{I}_{\Sigma}$
3. 对每个稳定段 $S\in\mathcal{S}_{\Sigma}$，构造其段级身份映射

$$
\phi_S:K_{\Sigma}(S)\to P
$$

4. 由这些段级身份映射与 issue 区间上的补充定义，共同构造全局帧级结果

$$
R_{\Sigma}:F_{\Sigma}\times P\to \mathcal{Q}.
$$

本文档到此为止，不再规定：

- 如何求 $\mathcal{S}_{\Sigma}$
- 如何求 $\mathcal{I}_{\Sigma}$
- 如何构造 $\phi_S$
- 如何在 issue 区间上定义 $R_{\Sigma}$

这些都属于后续算法、系统设计或人工流程的问题，不属于本定义文档。
