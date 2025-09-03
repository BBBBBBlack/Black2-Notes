# Glider Cache

### Motivation

* 深度学习模型是离线进行的，在硬件预测器上效果差
  * 一个程序在运行时表现出时变相位行为
  * 不同程序的行为差别大

* 模型太大无法在芯片上实现
* 模型很慢，通常需要几毫秒才能产生预测，而硬件预测器通常需要在**纳秒内**进行预测

### Background

#### Hawkeye Cache

一种内存放置策略（replacement policy）

<img src="..\..\assets\image-20250901171344751.png" alt="image-20250901171344751" style="zoom:75%;" />

* OPTgen：最优解生成器

  * OPT/Belady算法：每次选择淘汰的页面是以后永不使用或在最长时间内不再被访问的

  在一段**已经发生过**的内存访问记录（trace）上模拟Belady算法 —— trace已知，可以百分比确定每一次选择的淘汰页面符合上述Belady的要求

  在有内存访问指令时，Belady判断这次访问加载的数据是否应该被长时间保留在缓存中（如何判断 —— 数据在被淘汰之前成功地被再次访问了，则应该被长时间保留在缓存中）

  * 若最优解认为应该保留，OPTgen 为该条指令生成一个**缓存友好型 (cache-friendly)**的标签

  * 如果最优解认为应该淘汰或不缓存，，OPTgen 为该条指令生成一个**缓存厌恶型 (cache-averse)**的标签

* Hawkeye Predictor

  分类器，预测内存访问指令是否为缓存友好型

  * 缓存友好型 —— 这次访问加载的数据以高优先级插入
  * 缓存厌恶型 —— 这次访问加载的数据以低优先级插入

### Design

#### overview

* 无约束离线缓存模型：使用带有注意力机制的LSTM，输入完整的、有序的load指令 PC 序列
* 离线分析：发现指令的出现比其顺序更重要
* 简化的在线模型：构建SVM（降低了硬件实现的复杂度，同时依然保持了很高的预测准确率），输入不重复的、无序的load指令PC

### Evaluation

**benchmark**：SPEC CPU2006、SPEC CPU2017、GAP

* 内存敏感型：LLC MPKI>=1
* 用Simpoint为每个benchmark生成10亿条指令



**多核工作负载**：SPEC有很多种应用程序的trace，从中选取4种应用程序的trace为一种组合，让它们**同时、分别**跑在4个核心上——衡量Glider Cache在多CPU环境下的性能指标

* 4个trace若有先执行完毕的从头再开始执行。直到最慢的trace执行完
* 计算相对性能：LLC为4个CPU共用的，为计算该程序在多核环境下，与其他程序**共享和竞争缓存**时的实际性能：
  * weighted speedup（IPC评估系统整体性能）：`sum(IPC_Share/IPC_Single)`

**离线evaluation**：用ChampSim运行应用程序生成的LLC访问轨迹来评估模型

**对比替换策略**：Hawkeye、Perceptron



##### 离线环境下模型的精确度

在理想条件下，这些学习算法的理论预测准确率

ISVM：Glider Cache用在在线中的预测器

<img src="..\..\assets\image-20250902195105926.png" alt="image-20250902195105926" style="zoom:50%;" />

##### 在线环境下模型的精确度

真实情况下策略的准确率

<img src="..\..\assets\image-20250902195455410.png" alt="image-20250902195455410" style="zoom:60%;" />

##### 单核表现

<img src="..\..\assets\image-20250902200213270.png" alt="image-20250902200213270" style="zoom:80%;" />

<img src="..\..\assets\image-20250902200322946.png" alt="image-20250902200322946" style="zoom:80%;" />