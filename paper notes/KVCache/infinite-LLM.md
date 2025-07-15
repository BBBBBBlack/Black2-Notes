### 挑战一

KV cache在自回归的过程中不断扩展，占用的内存不断增大，而其它层的张量对内存的需求不变（如全连接网络层等等）

此时，由于KV Cache的扩增，需要增加GPU的数量，但这导致了其余层被划分为更细的粒度，而使资源利用效率更低

### 挑战二

自回归设计所生成的文本长度在生成过程结束之前是未知的，无法对资源进行预分配

如果内存超过当前实例gpu的容量，则必须将整个任务转移到具有更多gpu的实例上，耗费了更多的资源

如果一开始就为一个请求分配更多的gpu，当它生成的文本较短时，又导致了资源浪费

## 解决：

### DistAttention

* 原本的 attention：


$$
m_{g}=max(QK_{1},...,QK_{seq})\\\text{Attention}(Q,K,V)=\sum_{i=1}^{seq}\frac{\exp(QK_i^T-m_g)}{\sum_{j=1}^{seq}\exp(QK_j^T-m_g)}V_i
$$
  <img src="..\assets\image-20241030184820485.png" alt="image-20241030184820485" style="zoom:70%;" />

  <img src="..\assets\image-20241012113532636.png" alt="image-20241012113532636" style="zoom:50%;" />

* 将一个sequence的tokens划分为b个子块：其中第j个子块
  $$
  m_{j}=max(QK_1,...,QK_{seq_p}),e_j=\sum_{i=1}^{seq_p}\exp(QK_i^T-m_j)\\MA_j(Q,K,V)=\sum_{i=1}^{seq_p}(\exp(QK_i^T-m_j)V_i)
  $$
  将Q传入其他的远程实例，计算MA_j、m_j、e_j，再将以上三个值传入本地实例进行聚合
  $$
  m_g=max(m_1,...,m_b),e_g=\sum_{j=1}^be_j\exp(m_j-m_g)\\\text{Attention}(Q,K,V)=\sum_{j=1}^b\frac{MA_j\exp(m_j-m_g)}{e_g}
  $$
  <img src="..\assets\image-20241030190639677.png" alt="image-20241030190639677" style="zoom:70%;" />

允许KV Cache放置于多个实例上（而非只有本地实例），充分利用云资源



### 调度方法

* 如果一个实例将其KV Cache的一部分卸载到远程，如何确定适当的大小？性能增益和开销是什么？
* 如果一个实例借出一些空间，应该使用多少空间？
* 在实例众多的情况下，如何确定使整体绩效最大化的借贷关系？

Debtor——借用内存的实例

Creditor——借出内存的实例

<img src="..\assets\无标题.png" alt="iefewf677" style="zoom:100%;" />

KV Cache在云上各个实例的分配方法，使全局吞吐量最大化



### 系统实现

* gmanger

  集中式管理器，跟踪每个请求上的KV Cache位置，维护在request placement map请求放置映射中，并当新的KV Cache生成时，决定将它放在哪里

* rmanger

  一个实例一个，记录该实例的KV Cache使用情况

* 交互协议

  * 每个rManager使用心跳API向gmanger报告其本地状态

    {

    ​	[req_id, inst_id, num_blocks, local],

    ​	[req_id, inst_id, num_blocks, local],

    ​	...

    }

  * gManager将这些条目相应地更新到全局请求放置映射中

  * gManager使用move_kvcache API调度其请求放置决策

  * 源debtor调用try_move_kvcache API，以便在传输真正的KVCache数据之前尝试在目标实例上保留空间（gmanger的调度有可能过时，如未调度时，目标Creditor已经没有足够的空间）

  * 目标Creditor接收多个并发的try_move_kvcache（先来先服务）

  * 如果源debtor收到目标Creditor的允许信号，则开始传输数据，否则轮询，直到gmanger的下一个指令









## 实验结果



### 实验设置

#### 环境

4个节点和32个gpu的集群，每个节点有8xNVIDIA A100 (80GB) gpu，gpu在每个节点内通过NVLink （600GB/s）连接，在节点间通过以太网（125MB/s）连接

#### 模型

LLaMA2，包含三种不同的型号尺寸：7B、13B、70B

#### Trace

（）

<img src="..\assets\image-20241112035042111.png" alt="image-20241112035042111" style="zoom:70%;" />

#### Baseline

* vLLM-multi——与Infinite-LLM具有相同数量和并行配置的vLLM实例
* vLLM-single——单个vLLM实例
* 

![image-20241112035514006](..\assets\image-20241112035514006.png)



使用不同请求速率时的吞吐量延迟变化

从左到右，轨迹上下文长度分布的标准偏差减少，而实例数量从上到下增加

性能增益随着标准偏差（表明长度分布更加不均匀）和实例数量的增加而增加。这是因为更不均匀的长度分布或更多的实例数量会导致不同实例之间的资源需求差异更大，从而增强了跨所有实例统一资源管理的好处

<img src="..\assets\image-20241112035715944.png" alt="image-20241112035715944" style="zoom:80%;" />

从上到下，从左到右，我们观察到Infinite-LLM的性能增益随着上下文长度范围的扩大而增长。这是由于vLLM的静态模型并行性将模型分散到更多的gpu上，导致非注意力部分的效率降低，并显著降低了系统有效处理较短请求的能力，而Infinite-LLM为非注意力部分保持了适当的模型并行性策略，从而保持了它们的性能