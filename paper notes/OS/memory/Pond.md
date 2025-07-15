在云平台上，公共云客户以虚拟机（VM）的形式部署他们的工作负载，为此他们获得了性能接近专用云的虚拟化计算，但不必管理自己的本地数据中心

# 面临问题

### Memory stranding

​        当云客户启动VM时，VM将所有内存都预分配在其虚拟 CPU 所在的 NUMA 节点上，这种静态预分配的模式有助于使用虚拟化加速器（virtualization accelerators，让虚拟机拥有更高性能的技术，比如直接用网卡或 GPU。这些加速器要求虚拟机的内存不能随便改动，所以需要预先绑定在本地 NUMA 节点上）

​		**内存搁浅（Memory stranding）**：服务器上所有内核连同它们预分配的一块本地NUMA节点上的内存都被租出去了；此时还剩下一些内存，而内核已经用完了

* 这种内存搁浅现象会随着分配给VM的CPU占比的提升而越来越严重：
  
  <img src="..\..\assets\image-20250413034631930.png" alt="image-20250413034631930" style="zoom:50%;" />
  
  x轴：CPU使用率
  y轴：内存搁浅的比例
  |------------|之间：5%/95%的cluster的内存搁浅比例小于|这个点
  蓝线：所有cluster内存搁浅比例中位数
  	（又：这不是0或1的问题，在CPU未被完全用完时，也会发生内存搁浅，因为CPU使用率越高，剩余内存越少，一些有较大内存需求的VM无法使用）
  
* 几乎所有虚拟机都可以装入一个NUMA节点

* 收益曲线快速趋稳；pool 分配比例越大，节省的DRAM越多；

  <img src="..\..\assets\image-20250413040938769.png" alt="image-20250413040938769" style="zoom:50%;" />
  
  x轴：pool size
  
  y轴：在这种 pool size配置下，整个集群里需要预分配多少物理 DRAM
  
  各种颜色的线：每个 VM 有 10%、30%、50% 的内存来自于共享内存池（其余来自本地 DRAM）
  
  **在pool size=2~16时，整个集群所需的DRAM数随着pool size下降很快，而在pool size>16时，则相反（使用小池）**
  
  **每个 VM 来自pool的memory越多，整个集群节省的DRAM越多，但性能风险越高（用 zNUMA + ML 来规避这个问题）**

### Untouched Memory

VM在启动时预分配了大量的内存，但在实际运行时，有一部分的内存没有被使用

有大量untouched memory可以分解，而不会造成性能损失：

* VM内存使用情况差异很大
* 在untouched memory最少的集群中，仍有超过50%的虚拟机拥有超过20%的未触及内存
* 挑战在于**（1）预测VM可能拥有多少未触及的内存，以及（2）将VM的访问限制在本地内存**

### 工作负载对内存延迟的敏感性

<img src="..\..\assets\image-20250413051749795.png" alt="image-20250413051749795" style="zoom:80%;" />

x轴：158 个不同的 workloads

y轴：相比于访问本地NUMA节点的内存，通过CXL访问远程内存延迟增加的百分比

在小池内（pool size = 8~16 socket）：182% latency（约 142ns）

在大池内（pool size > 16 socket）：222% latency（约 255ns）



CXL对158个workload整体性能的影响

<img src="..\..\assets\image-20250413052147464.png" alt="image-20250413052147464" style="zoom:55%;" />

当通过CXL访问远程内存延迟相比于访问本地NUMA节点延迟增加182%或222%时，有y%的workload性能下降x%以下

142ns中：

​	一些工作负载受到的影响较小：有26%在CXL下的性能下降不到1%。另外17%的工作负载的性能下降不到5%

​	一些工作负载受到严重影响：21%的工作负载在CXL下性能下降>25%

255ns中：

​	23%在CXL下的性能下降不到1%。另外14%的工作负载的性能下降不到5%

​	超过37%的工作负载在CXL下性能下降>25%

**有些工作负载对分解的内存延迟不敏感，但有些工作负载受到了严重影响，Pond需要有效地识别敏感的工作负载**



# Design

PDM：相对于完全在NUMA本地DRAM上运行工作负载，允许的速度减慢

### 硬件层——EMC（外部存储控制器）

**内存管理**

<img src="..\..\assets\image-20250414140206506.png" alt="image-20250414140206506" style="zoom:96%;" />

multiheaded device（MHD，多头设备）：EMC提供多个CXL端口（CXL 是跑在 PCIe 电缆上的新协议，这里CXL 利用 PCIe 5.0 的物理通道——128个PCIe5.0物理通道，跑了16个8通道的CXL——但使用了自己的协议栈），EMC通过主机管理的设备内存（HDM）解码器在每个端口上向主机公开其全部容量

Pond以1GB内存片的粒度动态分配内存，在给定时间，每个切片最多分配给一个主机

DDR5 memory controllers (MC)：DDR5——动态随机访问内存（DRAM）标准，CXL端口通过片上网络（NOC）与DDR5内存控制器（MC）通信

**结构设计**

<img src="..\..\assets\image-20250414141354540.png" alt="image-20250414141354540" style="zoom:100%;" />

EMC结构：和AMD Genoa的IOD相似

8-sockets——1/2IOD

16-sockets——1IOD

32-sockets——CXL交换机+多头EMC（8个主机连一个switch，8个switch连4个EMC），1/2IOD？

**延迟分析**

<img src="..\..\assets\image-20250414143153724.png" alt="image-20250414143153724" style="zoom:90%;" />

Core/LLC /Fabric：L1 → L2 → L3（LLC） → miss → fabric（芯片互联）

主要延迟在CXL Port、Re-Timer、Switch

### 系统软件层

**Pool Manager (PM)**

PM和EMC放置在一个刀片上，连接CPU sockets和EMC

* 实现池级内存分配的控制路径

  * Add_capacity(host, slice)：PM使将要分配slice的主机的驱动程序产生一个中断 -> 主机驱动程序与操作系统内存管理器通信，使内存联机 -> EMC在slice偏移处将该主机id添加到其权限表中

  * Release_capacity(host, slice)：PM使将要释放slice的主机的驱动程序产生一个中断 -> 主机驱动程序与操作系统内存管理器通信，使内存卸载 -> EMC在重置其权限表中

* 防止池内存碎片化

  host agents 和 drivers可以分配池内存并导致碎片化。因此，Pond划分了一个专用的 **本地内存分区**，仅对管理程序可用，并禁止它们使用池内存（即使有 pool memory 可用）。host agents 和 drivers在主机本地内存分区中分配内存

**故障管理**

一台主机所需要的pool memory只能分布在一个EMC连接的DRAM上

* EMC故障：只影响该EMC连接的DRAM上有内存slices的VM
* CPU/主机故障：被隔离，相关联的pool memory被重新分配给其他主机
* Pool Manger故障：阻止pool memory的重新分配

**将pool memory暴露给VM**

VM将pool memory视为zNUMA，所以优先从本地NUMA中分配

​	实现细节：管理程序通过在SLIT/SRAT表中的node_cpuid中添加一个没有条目的内存块（node_mmblek）来创建zNUMA节点

**重新配置内存分配**

* 当VM迁移到另一台主机时
* 当触发 page fault（页故障）时（某个页面性能太差，比如频繁跨 NUMA 访问）

临时禁用virtualization acceleration

* 当性能不佳时

  * 何时性能不佳：

    监视器查询管理程序和硬件性能计数器，并使用延迟敏感性的ML模型（**sensitivity model**）来确定VM的性能影响是否超过PDM。若超过，监视器要求其缓解管理器通过管理程序触发内存重新配置


临时禁用virtualization acceleration，把所有 pool memory 拷贝回本地内存，再启用virtualization acceleration

**不透明虚拟机的遥测**

* PMU：CPU 内核中的专用逻辑块，用于记录计算系统上发生的特定硬件事件

  使用TMA[自上而下分析法](Top-down Microarchitecture Analysis Method.md)

* 使用虚拟机监控程序遥测来跟踪VM的untouched memory

### 分布式控制平面层

* 预测、调度

  <img src="..\..\assets\image-20250416032251566.png" alt="image-20250416032251566" style="zoom:60%;" />

  * VM发送请求
  * VM scheduler 向**ML System(A)** 查询关于为VM分配多少本地内存的预测
  * VM scheduler 通知 PM 目标主机的池内存需求
  * PM 使用到EMC和主机的配置总线将pool memory分配给VM
  * 将VM信息发送给管理程序，以便QoS进行监控
  * （VM启动时，pool memory卸载工作异步进行）

* QoS监控

  * 监视器查询管理程序和硬件性能计数器，并使用延迟敏感性的ML模型来确定VM的性能影响是否超过PDM
  * 若超过，监视器要求其缓解管理器（B2）通过管理程序（B3）触发内存重新配置。重新配置后，VM仅使用本地内存

### 预测模型

<img src="..\..\assets\image-20250416232245821.png" alt="image-20250416232245821" style="zoom:100%;" />

#### Predictions for VM scheduling (A)——VM启动时请求Pool Memory时

* 检测是否存在和当前VM的请求具有相同元数据（客户id、VM类型和位置）的VM

  * 若有，**sensitivity model**预测该VM是否对内存延迟敏感：若不敏感（性能在PDM内）只使用池内存

  * 若无，或预测为敏感，通过通用VM元数据（如客户历史、VM类型、客户操作系统和位置），预测其生命周期内的untouched memory

    * 若UM=0，不分配池内存

    * 若UM>0，将所需pool memory按GB对齐，四舍五入

      若高估了UM，参考**重新配置内存分配**性能不佳的情况



#### QoS monitoring (B)——QoS监控时

对于zNUMA VM，Pond会监控在调度过程（A）中是否为VM分配了太多的Pool Memory

* 调度过程（A）中是否为VM分配了太多的Pool Memory（zNUMA是否被访问？）
  * 若是，**sensitivity model**预测该VM是否对内存延迟敏感
    * 若敏感，整个迁移到local DRAM
    * 若不敏感，继续监测

#### 两个模型

##### Lantency Insensitive?

<img src="..\..\assets\image-20250416232521415.png" alt="image-20250416232521415" style="zoom:90%;" />

特征：PMU检测到的各种指标

标签：池内存相对于NUMA本地内存是否速度减慢<PDM

获取样本：

* 离线测试：在内部平台上，把同一个 VM 工作负载分别跑在本地内存和池内存上，比较性能下降是否<PDM
* A/B测试：A组使用本地内存，B组使用池内存，同时在线跑工作负载，若性能差异< PDM，则延迟敏感

##### Untouched memory?

<img src="..\..\assets\image-20250417034414485.png" alt="image-20250417034414485" style="zoom:45%;" />

特征：VM元数据

标签：每个VM生命周期内的最小untouched memory

#### 参数化

false positives (FP)：把内存敏感的VM判断为内存不敏感

overpredictions (OP)：预测的untouched memory太多，VM使用了zNUMA中的空间

TP：性能下降<PDM的VM的百分比

Pond 旨在最大化分配到 CXL 池上的平均内存量，所以有延迟不敏感性 (LI)的VM和VM中的nutouched memory要尽可能多

但要保持错误预测率 (FP) 和超预测率 (OP) 低于目标虚拟机百分比 (TP)

公式：

<img src="..\..\assets\image-20250417040827830.png" alt="image-20250417040827830" style="zoom:45%;" />

# 实验

* zNUMA的有效性

  <img src="..\..\assets\image-20250417155056929.png" alt="image-20250417155056929" style="zoom:80%;" />

  假设zNUMA上的untouched memory的大小是准确的

  48h内zNUMA被访问的情况（Video）:视频工作负载向zNUMA节点发送的内存访问不到0.25%。同样，其他三个工作负载向zNUMA节点发送0.06-0.38%的内存访问

* UM超预测对性能的影响

<img src="..\..\assets\image-20250417155730803.png" alt="image-20250417155730803" style="zoom:100%;" />

* 预测模型的性能

  * 延迟敏感预测模型

    <img src="..\..\assets\image-20250417162823074.png" alt="image-20250417162823074" style="zoom:90%;" />

    随机森林和取PMU采集的其中一个指标做预测的效果对比

    x轴：预测为LI的workload的百分比

    y轴：FP，把内存敏感的VM判断为内存不敏感的百分比（slowdown>PDM）

  * untouched memory预测模型

    <img src="..\..\assets\image-20250417164150879.png" alt="image-20250417164150879" style="zoom:90%;" />

    GBM模型和一个启发式策略（所有VM分配固定比例的UM）做预测的效果对比

    x轴：预测分配的池内存（占 VM 总内存的比例 * 时间）

    y轴：超预测的百分比

  * 两个模型结合

    评价指标：scheduling mispredictions——工作负载超过PDM的概率

    <img src="..\..\assets\image-20250417171654046.png" alt="image-20250417171654046" style="zoom:100%;" />

* 总DRAM节省

  <img src="..\..\assets\image-20250417173121465.png" alt="image-20250417173121465" style="zoom:90%;" />
