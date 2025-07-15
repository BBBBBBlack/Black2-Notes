# Pmem（已经寄了）

persistent memory——持久性内存

通过内存总线和CPU相连

大容量持久存储（外存特性） + CPU以字节粒度访问（内存特性）

<img src="..\..\assets\6878ac7c6f1f33d637591c6a1aad0159.png" alt="在这里插入图片描述" style="zoom:70%;" />

## 内存模式

DRAM作为L4 Cache，Pmem作为主存（大容量+易失）

<img src="..\..\assets\image-20250105235327201.png" alt="image-20250105235327201" style="zoom:40%;" />

DRAM作为Pmem的Cache，采用直接映射的方式[直接映射](./SRAM DRAM.md)

## 无CPU的NUMA

用户可以同时看到DRAM和Pmem两个NUMA node（易失）

如果延迟敏感，那就绑定DRAM分配；反之可以绑定Pmem分配；

需要大容量时，可以指定优先DRAM分配，需要高带宽时，可以指定交错DRAM和Pmem分配

<img src="..\..\assets\b5d800f0c7c2393b2ee57902fb2a3611.png" alt="在这里插入图片描述" style="zoom:50%;" />

每个数据只能在一个位置上（不能复制多个副本）

<img src="C:\Users\black\AppData\Roaming\Typora\typora-user-images\image-20250106010124026.png" alt="image-20250106010124026" style="zoom:55%;" />



## APP Direct

将 NVM 作为文件系统、单字节或块可寻址设备文件公开给应用程序

为应用程序提供对其 NVM 分配的显式控制
