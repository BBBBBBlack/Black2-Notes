## 挑战

对于静态的并行策略——模型并行（例如张量并行）、序列并行

* 请求的输入长度方差变大，**不同请求**的计算需求不同
* **同一请求在不同阶段**的资源需求有很大差异

将 GPU 组织成多个组，每个组部署一个LLM实例，并采用不同的并行策略来处理特定序列长度范围或特定阶段的序列

* 迁移KV-Cache的通信开销大
* 组之间的隔离，不同组之间的 GPU 内存无法一起用于服务长序列长度的请求，从而导致 GPU 内存碎片



## LoongServe

<img src="..\assets\image-20241116021738668.png" alt="image-20241116021738668" style="zoom:50%;" />



### elastic instance（弹性实例）：

最小的独立执行单元。每个都维护模型权重的副本，并在**同等数量**的 GPU 上采用**统一**的模型并行性

动态地将自己组织成一组不相交的 ESP 组，以不同的可配置并行度并行处理批量请求；支持弹性扩展和缩小

<img src="..\assets\image-20241116024816210.png" alt="image-20241116024816210" style="zoom:50%;" />
$$
(B_i,I_j)第j个批次的第i次迭代\\
预填充阶段的计算复杂度远高于解码阶段，在预填充阶段之后要缩小批量\\
(B_1,I_1)\rightarrow (B_1,I_2)\\
随着生成的 token 越来越多，解码阶段的计算复杂度增加，并行组中的 GPU 内存可能会被键值缓存填满，导致需要扩展并行组\\
(B_2,I_2)\rightarrow(B_2,I_3)\\
为了给预填充阶段预留更多的资源，全局管理器在其好处超过缩小的开销时\\
(B_2,I_3)\rightarrow (B_2,I_4)
$$

* scale down

  如何将并行度大的group产生的张量有效地迁移到并行度小的group？

  * 现有方案：在预填充阶段后将键值张量从并行组 R 迁移到新的并行组 R'

    迁移开销大，内存碎片问题

  * 新方案——主动迁移（**proactive scaling-down mechanism**）

    <img src="..\assets\image-20241116225811546.png" alt="image-20241116225811546" style="zoom:50%;" />
    
    decoder阶段需要prefill阶段提示词生成的所有KV Cache：
    
    在序列并行时，每个实例从相邻实例接收KV Tensor、计算注意力并将其发送到下一个实例，除此之外，前两个实例还选择性地将KV Tensor保存到其group中的key-value cache pool中
  
* scale up

  确保新添加的实例能够有效地参与正在进行的计算，而不产生额外的开销

  * 现有方案

    TP（张量并行）等，仅支持单个实例中跨多个GPU的分布式解码计算，当某个实例的GPU内存等资源不足时，必须将批量中的部分请求迁移到另一个实例，通信开销大；要求请求的全部或大部分键值张量必须存储在单个实例中，导致内存碎片问题

  * 新方案——多主分布式解码

    **单主分布式解码**：一个组里有多个实例，指定其中一个实例为主实例，主实例计算请求的所有token的QKV，将KV保存在实例的缓存池中，将q分配到各个实例上，各个实例使用计算self-attention的输出，传回主实例等待下一步运算
    
    **疑问：其他非主实例的KV Cache怎么获得呢？**
    
    ​	局限性：
    
    * 主实例中未使用的slot要足以存储下一次迭代生成的KV张量，导致内存碎片问题
    * 像FFN这样的本地层都是在主实例上执行的，因此当解码阶段变得计算密集时，其性能受到主实例中的计算资源的限制
    
    **多主分布式解码**：
    
    <img src="..\assets\image-20241129013715037.png" alt="image-20241129013715037" style="zoom:55%;" />
    
    当主实例交换查询张量时，它们之间的通信可以与其所控制的请求的本地注意力计算重叠
    
    **疑问：某个请求的q可以和非本请求生成的KV Cache做注意力运算吗？**

### unified distributed key-value cache pool（统一分布式KV-Cache池）：

跨弹性实例以token粒度存储请求的KV-Cache——减少GPU内存碎片



### global manager（全局管理器）：

管理请求、弹性实例、统一分布式KV-Cache池

* Dispatcher（调度器）：

  将新到达的请求按照全局管理器的要求调度到一组特定的弹性实例

  

* Elasticity Controller（弹性控制器）：

  根据全局管理器生成的 DoP 和扩展计划，命令弹性实例更新其配置，以形成相应的 ESP 组并并行处理请求

全局管理器监视请求的进度、弹性实例的资源使用情况以及键值缓存池以更新其决策

#### 四个步骤

* dispatching：

  从待处理队列 P 中选择请求子集 R_p 来执行当前迭代中的预填充阶段

  按照先到先服务 (FCFS) 的顺序扫描 P

  * GPU Memory —— 基于当前状态和请求的最大序列长度考虑未来最大KV Cache消耗，如果可能引发驱逐（算到一半GPU内存不足），则不将该请求添加到 R_p

  * GPU Computing —— 当 R_p 的迭代时间超过临界点（一个通过分析预填充批次受内存限制的迭代时间上限估计出的时间点。在此之前，向 R_p 添加更多请求可以提高 GPU 计算的效率；在此之后，只会延长执行时间，而效率的提高可以忽略不计）时，global manager 停止向 R_p 添加更多请求

    假设添加新的请求会抢占原本R_p中的请求，则抢占对输出Token的延迟为（**抢占Bp,i的成本**）
    $$
    \mathrm{Cost}=\sum_{r\in B_{p,i}}\frac{T(R_p\cup R_{p,i}^{\prime},E_p\cup G_{p,i})}{r.\mathrm{output~len}}\\
    B_{p,i}:请求R'_{p,i}将会被分到的那个batch?\\
    T(R_p,E_p):请求集R_p在被其占用实例集E_p上的迭代时间\\
    r.output\space len:\text{the number of existing output tokens}\\
    $$
    **执行R'p,i的增益**
    $$
    \mathrm{Gain}=\sum_{r\in R_{p,i}^{\prime}}\frac{(\mathrm{AvgLat}_{\mathrm{d}}-\min(B_{p,i}.\mathrm{exec}_\mathrm{time}))^+}{r.\mathrm{input}_\mathrm{len}}\\
    AvgLat_d:解码阶段完成请求的平均执行时间\\
    解码阶段请求的执行时间:\min(B_{p,i}.\mathrm{exec}_\mathrm{time}))^+\\
    相减:在最坏情况下 R′_{p,i} 必须等待解码批次的时间
    $$
    若增益大，则添加

    

* Elastic Instance Allocation

  为选出的R_p分配弹性实例

  首先将空闲实例分配给 R_p

  空闲实例未使用的KV Cache slot不够，R_p可以抢占少数未使用KV Cache slot的实例，以获得足够的KV Cache slot

  global manger 尝试将被抢占实例中的现有KV Tensor迁移到其他活动实例

  解决问题：是否将当前拥有最少KV Cache slot的实例分配给R_p？

* Batching

  为不同序列长度的请求分配不同的DoP（degrees of parallelism）——应该是指分配的实例内部的GPU个数

  global manager 根据请求的序列长度降序对请求进行排序，分配的弹性实例根据其位置和未使用的KV Cache slot的数量按升序排序
  
  动态规划：
  $$
  f[i][k]=min_{0\le j\le i,0\le l \le k,D[j,i]\le V[l,k]}(f[j][i]+T(R[j,i],E[l,k]))\\
  f[i][k]:使用前 k 个弹性实例时前 i 个请求的最小输入延迟\\
  T(R[j,i],E[l,k]):使用 l 到 k 的弹性实例时，从 j 到 i 的请求的输入延迟之和
  $$
  
* 

​		找到在f\[i\]\[k\]最小时，对应的实例l和请求j

* Elastic Scaling Plan Generation
  * 缩小规模：解码阶段的扩展性很差，其请求的最小最佳DoP是相似的，因此将模型并行度设置为启动时的最小最佳 DoP
  * 扩展规模：在GPU计算或GPU内存不足时进行，