## 多模态的特征

* 子模块异构性

  子模块的大小、计算需求、GPU利用率不同

* 各个子模块输入大小不平衡

* 批量要求大

  为对比学习提供更多的正负样本，以提高模型的鲁棒性







## 挑战

原本的并行策略（数据、张量、流水线）效率低下

* 数据并行（将整个模型复制到多个设备上并行处理不同的数据）：

  所有子模块在每个设备上都被配置。不同子模块之间的异构性和输入量不均衡导致计算规模和硬件利用率不均衡

  不同子模块共存减少了每个子模块的可用内存，限制了计算的批处理大小

  ​	—— a non-colocation solution

* 张量并行（将每一层的张量分割开放到不同的GPU上计算，再reduce）

  较小模块张量划分开销可能 > 其未划分时计算开销

​			—— an adaptive partitioning method

* 流水线并行（将模型按层划分，分配到不同GPU上执行，将global batch拆分成多个micro batch,在每个micro batch上进行forward和backward）

  样本数不够多，对比学习效果下降

  ​	—— a new pipeline parallelism scheme







## DISTMM构成



#### Modality-aware partitioner

model-level partitioning（模型级别的划分）

（Modality-aware partitioner first parallelizes submodules with **independent parallelism strategies** to satisfy memory constraints while maintaining low overheads.）

* 使用independent parallelism strategies并行子模块
  * 将的计算量平均分配到每个设备上
* 为不同的子模块提供不同的adaptive partitioning（张量、数据、流水线）



#### Data load balancer

为不同子模块提供不同数量的设备和合适的batch_size（batch dimension partitioning）

（设备数* batch_size=global batch_size?）

* 为每个模型分区（Modality-aware partitioner获得）分配设备数量和数据批处理大小

  <img src="..\assets\image-20241103172321992.png" alt="image-20241103172321992" style="zoom:50%;" />

  子模块副本数量越少，每个副本需处理的数据批量越大，对于较小的子模块，使用少副本，处理大批量数据效率高

  

#### Heterogeneity-aware placement manager

在具体物理设备上的位置（考虑到节点内部和之间的通信开销）

将同一模态中的子模块分区分组，靠近放置

将不同模态的子模块分区放置在单独的节点上

* 子模块内部

  * 由通信频率、通信数据量确定优先级
  * 优先级高的放置在节点内部，低的放置在不同节点上

* 子模块之间

  * 减少模块交互开销
    $$
    计算相似度的两个点积：\\
    局部图像特征向量·采集到的整个文本特征向量\\
    局部文本特征向量·采集到的图像特征向量\\
    \Rightarrow \\
    局部模态特征向量·相反模态特征向量
    $$

  * 减少all-reduce的开销

    <img src="..\assets\image-20241103180000829.png" alt="image-20241103180000829" style="zoom:50%;" />

    all-reduce通信量不随每个GPU处理的批量大小增大

    计算时间随每个GPU处理的批量大小增加

    通信时间占比减小



#### Pipeline executor

<img src="..\assets\image-20241103165317186.png" alt="image-20241103165317186" style="zoom:50%;" />

为每个子模块生成特定管道执行计划

mid-point synchronization：中间点，维护不同模态子模块之间模态交互的语义
$$
最大micro-batch 大小：\\
((M-M_s/P)/(M_a/P))/P\\
M:每个GPU的大小\\
M_s：用于存储一个batch的静态参数的内存\\
P：流水线级数 or \space micro-batch的数量\\
M_a：用于存储一个batch的activation \space memory的内存
$$

* batch-sync instruction（批处理同步指令）
  $$
  K=Rbs/Mbs\\
  Rbs:模态交互所需的batch\_size\\
  Mbs:micro-batch\_size
  $$

  * 将K个micro batch的 forward 输出拼成一个大小为batch_size的特征向量
  * 模态交互子模块forward采用以上特征向量
  * backward，生成特征向量相应的梯度
  * 将以上连续梯度分配给每个micro-batch特征向量对应的K个梯度

* DISTMM-Pipe scheduling（流水线调度）

  Gpipe——forward和backward之间被批处理同步指令分开，导致了较大的空闲期

  ![image-20241104024031422](..\assets\image-20241104024031422.png)

  

  * $$
    micro-batch\_size=Mbs/2,\\
    batch\_size=2K\\
    即1\space batch划分为4\space micro-batch
    $$

  * 属于不同K个微批的backward和forward以交错的方式执行

    ![image-20241104025639925](..\assets\image-20241104025639925.png)

  * 最大批处理大小：
    $$
    (M· P-M_s)/(2M_a)\\
    M· P-M_s：所有GPU可用于存储activation\space memory的总容量\\
    2M_a：batch\_size
    $$
    随P线性增长，可以通过扩展集群大小（增加流水线的级数）来保证模型质量要求

    