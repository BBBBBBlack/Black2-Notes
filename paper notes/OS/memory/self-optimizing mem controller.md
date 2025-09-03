# Self-Optimizing Memory Controllers

### Memory Controller

**cache miss**：当处理器尝试访问Cache时，所需的数据不在Cache中，要从主存DRAM中取

**DRAM结构**：

* 多个DRAM组成一个DIMM
* 多个**bank**组成一个DRAM，每个bank是一个按 `x行 * y列` 组织的二维数组
* 一个bank一次只能访问一行，每个bank包含一个**row buffer**，要访问bank中的某个位置，必须确保该行位于row buffer 中

**memory controller**接收来自处理器的cache miss、write back请求，放入transaction queue中，发出适当的DRAM命令以满足这些请求

* 对于一个请求，需要按序执行以下命令：
  * precharge：关闭旧行，以便后续activate新的行——从DRAM存储单元读取数据的过程本身是破坏性的。要在关闭旧行时，将数据写回（write back）memory array
  * activate：地址总线传送来地址，activate将该地址对应的行从memory array送到row buffer
  * read / write：对已经从DRAM --> row buffer 的行数据进行read / write操作，附带列地址定位需要read / write的数据的具体位置，将从该地址开始，一个cacheline大小的数据从row buffer传送到cache
    * 行地址：用来选择DRAM bank中的“哪一行”
    * 列地址：用来指定在那一行中，“从哪个位置开始”进行数据传输

### Key Idea

将memory controller设计为RL agent，通过与系统其他部分的交互自动学习最佳内存调度策略

### Overview

<img src="..\..\assets\image-20250903165955398.png" alt="image-20250903165955398" style="zoom:70%;" />

<img src="..\..\assets\image-20250903170101567.png" alt="image-20250903170101567" style="zoom:70%;" />

### 算法流程

<img src="..\..\assets\image-20250903170359751.png" alt="image-20250903170359751" style="zoom:200%;" />

执行命令 ➡ 获取state 和reward ➡ 从合法的命令中选取一条（greedy epsilon） ➡ 查表获取Q值（state, action） ➡ 更新上次的Q值 ➡ 执行新命令……

#### Q-value table设计

CMAC

<img src="..\..\assets\image-20250903171205457.png" alt="image-20250903171205457" style="zoom:75%;" />

* coarse-grain Q-value tables：将庞大的状态空间压缩成一个较小、可管理的表格（多个邻近、独立的系统状态聚合到一个格中，共用一个Q值）
* CMAC使用多个coarse-grain Q-value tables，这些表相互之间有随机的偏移和重叠
* 当系统更新一个状态的Q值时，与之相似的其他状态的Q值也会被“泛化”更新，实现了跨状态学习