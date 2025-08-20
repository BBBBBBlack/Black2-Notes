# 一些废物motivation

#### 说明1：

不同应用程序的内存访问方式不同

<img src="..\assets\image-20250818161220827.png" alt="image-20250818161220827" style="zoom:80%;" />

当把应用程序从DRAM内存迁移到NVM上时，不同类型的应用程序会因为不同的性能瓶颈而受到影响

不同类型的应用在NVM上表现出的**不同**的性能瓶颈，反向证明了它们内在的内存分配与访问模式是不同的 

* GraphMat 和 X-Stream 这样的流式处理（Streaming oriented）应用 >> 需要**一次性**读取或写入大量**连续**的数据 >> 对NVM的低带宽敏感
* 其他应用（如键值存储、数据库） >> 内存访问可能更**零散**，每次只读写少量数据，但**访问频繁** >> 对NVM的高延迟敏感



#### 说明2：

同一应用程序在不同阶段的内存分配方式不同

内存分配的生命周期通常是**双峰的（bimodal）**[Hemem]

* 服务启动，程序会一次性申请非常大块的内存空间，这些内存用来存放核心数据，一旦加载进来，在程序运行期间就一直存在，不会被释放
* 服务运行，会使用小块的内存对象，它们在很短时间后就会被释放（例如用户请求）

##### GraphMat

<img src="..\assets\image-20250818165251229.png" alt="image-20250818165251229" style="zoom:80%;" />

* 三种数据结构
  * 邻接矩阵 (Adjacency Matrix)、顶点数据（Vertex Data）——在图计算**开始**时创建、在整个算法的迭代过程中持续存在
  * 稀疏向量 (Sparse Vector)——**每次迭代**都会被重新创建

##### graph processing on the GAP 

Kronecker powerlaw graph（幂律图）——一种结构很不均匀的图结构，有局部性：某些节点会被频繁访问，类似于真实的社交网络

图访问

* 在算法的第一次或前几次迭代中，系统没有关于图中哪些节点和边是“热点”的先验知识 >> 要对对整个图进行广泛的探索 >> 大量冷数据被访问
* 经过几次迭代后，热点数据集基本稳定下来，内存迁移的算法（如Hemem将冷数据迁移到NVM，把热数据迁移到DRAM）算法的后续迭代会反复集中访问这些热点数据

识别热点计算在一个图中，有多少条最短路径会经过某一个特定的节点——衡量一个节点在整个网络中的重要性

（以Hemem - PT Async为例）

<img src="..\assets\image-20250819172735622.png" alt="image-20250819172735622" style="zoom:70%;" />

* 扫描页表确认冷热数据，将识别出的热数据从NVM迁入DRAM，将不太热的数据从DRAM写入NVM（由于识别缓慢，热点被高估，导致来回迁移，写入量很多）
* 后期稳定后，写入量变少、趋于一致

##### Spark RDD

<img src="..\assets\image-20250819202011070.png" alt="image-20250819202011070" style="zoom:50%;" />

* RDD

  内存中的只读数据集合，可分片存放。数据在内存的多个RDD之间进行传递，避免了读写磁盘的开销

  针对RDD的操作：

  <img src="..\assets\image-20250819212006447.png" alt="image-20250819212006447" style="zoom:42%;" />

  * 转换（Transformation）：map、filter、groupBy、join等，只是记录，针对RDD全集（粗粒度）
  * 动作（Action）

  DAG：按照RDD的依赖关系构建，使得中间结果可不写入磁盘，直接输入给下一个操作；可溯源

  <img src="..\assets\image-20250819212625450.png" alt="image-20250819212625450" style="zoom:45%;" />

  * 窄依赖：一个父RDD的分区对应一个子RDD的分区/多个父RDD的分区对应一个子RDD的分区
  * 宽依赖：一个父RDD的分区对应多个子RDD的分区

  <img src="..\assets\image-20250819222752580.png" alt="image-20250819222752580" style="zoom:50%;" />

  遇到窄依赖，加入当前stage；遇到宽依赖，划分一个新的stage

  <img src="..\assets\image-20250819222933565.png" alt="image-20250819222933565" style="zoom:56%;" />

  窄依赖处理：在一个Executor内部以流水线方式全速运行——推测CPU是瓶颈

  宽依赖处理：数据必须先被前一个Stage的所有Task写入磁盘，然后通过网络进行Shuffle——推测网络与磁盘IO占比大

* Driver

  向资源管理器Cluster Manger申请资源，将应用程序的作业划分为不同的阶段，将每个阶段的任务调度到不同的Worker Node上执行

  <img src="..\assets\image-20250819203056615.png" alt="image-20250819203056615" style="zoom:35%;" />

  * 根据RDD的依赖关系生成DAG图
  * 将生成的DAG图提交给DAG Scheduler，由其将作业划分为多个阶段（Stage）
  * 将多个阶段提交给Task Scheduler，由其将任务分配给Worker Node执行（Worker Node主动申请，由Task Scheduler决定发给谁）
  * 任务执行完后，结果 >> Task Scheduler >> DAG Scheduler >> SparkContext >> 返回给用户或写入HDFS

* 工作节点（worker node）

  每个工作节点上有一个executor进程，下分为多个线程，每个线程可以运行一个任务

* 作业（job）

  由应用程序提交，一个作业划分为多个阶段，一个阶段里有多个任务，每个任务由executor中的一个线程执行

  <img src="..\assets\image-20250819202543686.png" alt="image-20250819202543686" style="zoom:30%;" />

总体流程：

* Driver向Cluster Manger 申请CPU、内存等资源
* Cluster Manger启动Worker Node上的Executor
* 将作业（一系列的任务）发送给Worker Node执行
* 执行结束后Worker Node将结果返回给Driver或写入文件系统HDFS