# NVDIMM（Non-Volatile Dual In-line Memory Module）



## 连接方式

将NVM插在内存卡槽DIMM上，内存总线直接访问

（相比之下，CXL插在PCle插槽，离CPU远，延迟较高）

## 三个标准

* NVDIMM-N 标准：在 2014 年第一次提出 NVDIMM-N 标准，主要针对 DRAM 的断电易失性，通过在 DRAM内存条上增加超级电容以及闪存介质，对断电时数据进行保护。在断电时，在电容的电源续航能力的作用下，NVDIMM-N设备内部控制器将DRAM中的数据迁移到闪存中，在突然断电的情况下保护数据，其性能和普通内存条是相同的。
* NVDIMM-F标准：2015年提出，NVDIMM-F原理是设计使用DIMM接口的闪存块设备，直接插入内存插槽，处理器直接通过内存总线访问设备，利用内存通道的高性能降低访问延迟。由于闪存介质本身性能限制，其性能仍低于普通内存，访问延迟在10微秒这个数量级，但是远远高于PCIe接口的闪存固态盘。
* NVDIMM-P标准：2016年提出，NVDIMM-P是一种综合NVDIMM-N 与NVDIMM-F的存储形态，想法是使用DRAM与闪存组成的混合存储架构，利用数据局部性原理，将DRAM作为闪存介质的高速缓存，其性能介于NVDIMM-N 以及NVDIMM-F之间，大约为100 纳秒，容量上还远大于NVDIMM-N，可以达到与NVDIMM-F一样的容量

## 访问方式

* Pmem
  * MMAP：绕过操作系统内核
  * 通过操作系统文件系统提供的API访问

* BLK

  Block Layer（简称[blk](https://www.kdun.cn/ask/tag/blk)）是一个用于管理块设备I/O操作的子系统，它介于上层的文件系统和下层的硬件驱动之间，负责处理数据在存储设备上的传输、缓存以及调度

  <img src="..\..\assets\neil-blocklayer.png" alt="[Block layer diagram]" style="zoom:90%;" />