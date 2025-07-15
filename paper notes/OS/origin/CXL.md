# Compute Express Link (CXL)

CXL is a low-latency, high-bandwidth link that supports dynamic protocol muxing of coherency, memory access, and IO protocols, thus enabling attachment of coherent accelerators or memory devices

## PCle 5.0

一种高速串行计算机扩展总线标准，用于连接计算机内部的各种设备、芯片，如固态硬盘、显卡等

点到点传输，采用低压差分技术，一条通道（Lane）在发送（TX）和接收（RX）方向上共有四条信号线。PCIe 5.0的单通道最大传输速率是32GT/s（支持x1，x2，x4，x8，x12，x16和x32通道数）

<img src="..\..\assets\image-20241227173620031.png" alt="image-20241227173620031" style="zoom:80%;" />

Root complex：简称RC，root complex主要负责PCIe报文的解析和生成。RC接受来自CPU的IO指令，生成对应的PCIe报文，或者接受来自设备的PCIe TLP报文，解析数据传输给CPU或者内存。

Endpoint：简称EP，PCIe终端设备，是PCIe树形结构的叶子节点。EP可以分为三类，legacy endpoint，PCI Express endpoint和Root Complex Integrated Endpoints (RCiEPs)。

Switch：PCIe的转接器设备，提供扩展或聚合能力，并允许更多的设备连接到一个PCle端口。它们充当包路由器，根据地址或其他路由信息识别给定包需要走哪条路径。

<img src="..\..\assets\image-20241227173706435.png" alt="image-20241227173706435" style="zoom:50%;" />

<img src="..\..\assets\bVbDVi" alt="image.png" style="zoom:40%;" />

TLP：事务层，Transaction Layer packet

DTLP：数据链路层，Data Link Layer packet

## CXL

和PCle一样，是用于连接计算机内部组件的高速接口技术，但PCle在不同设备之间通信的开销较高，CXL能连接CPU和外部的设备（如内存模块和加速器），使异构计算成为可能（不再一味地往CPU上加功能，而是将功能由专业的芯片实现封装，通过CXL连接到CPU）

三种设备：

* Type1：高性能计算里的网卡（PGAS NIC），它支持一些网卡的原子操作
* Type2：带有内存的加速器，包括GPU、FPGA等
* Type3：用作内存的Buffer，做内存的扩展

<img src="..\..\assets\image-20250103161758653.png" alt="image-20250103161758653" style="zoom:35%;" />

### 协议支持

* CXL.io——用于初始化、链接、设备发现和枚举以及注册访问的协议，为 I/O 设备提供接口，类似于 PCIe Gen5
* CXL.cache——拓展系统内存，允许 CXL 设备连贯地访问和缓存主机 CPU 的内存
* CXL.mem——允许 CPU 设备连贯地访问设备附加内存

