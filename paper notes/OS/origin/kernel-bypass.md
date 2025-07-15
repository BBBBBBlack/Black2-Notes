# DPDK

[参考1](https://gitcode.csdn.net/66c582508f4f502e1cfc5679.html?dp_token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6MzE3Mjg0MywiZXhwIjoxNzUwNjE0MzIxLCJpYXQiOjE3NTAwMDk1MjEsInVzZXJuYW1lIjoibTBfNjMyNzM3OTUifQ.8dsy5FmdQqLIDS7lLa0MfXo4vp94gifauPS__K9ZKKE&spm=1001.2101.3001.6650.12&utm_medium=distribute.pc_relevant.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7Eactivity-12-105587309-blog-147766448.235%5Ev43%5Epc_blog_bottom_relevance_base9&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7Eactivity-12-105587309-blog-147766448.235%5Ev43%5Epc_blog_bottom_relevance_base9&utm_relevant_index=23)

[参考2](https://blog.csdn.net/qq_39748830/article/details/147766448)

<img src="..\..\assets\image-20250616030638516.png" alt="image-20250616030638516" style="zoom:35%;" />

* 传统Linux网络数据流程：

  <img src="..\..\assets\v2-e5b74a94c337139661a560c3e3112355_1440w.png" alt="img" style="zoom:90%;" />

* DPDK网络数据流程：

  <img src="..\..\assets\v2-1c1128c6768dc3039f9a2f2cf4ea9985_1440w.jpg" alt="img" style="zoom:90%;" />

DPDK具体原理：

<img src="..\..\assets\image-20250616031843147.png" alt="image-20250616031843147" style="zoom:35%;" />

* 网卡会通过 DMA 将收到的数据写入内存中一段缓冲区，该缓冲区由用户态驱动（应用程序）通过大页内存（HugePages，将连续的大块物理内存分配给用户空间，在之后的mmap阶段，页表将使用更大的 page size（如 2MB）建立虚拟地址和物理地址之间的映射）预先分配，并将其物理地址告知网卡
* 内核态驱动使用 UIO 框架将网卡注册为 /dev/uioX 设备，从而暴露给用户态驱动使用
* 用户态的应用程序通过访问/dev/uioX文件实现对网卡分配的内存的mmap等操作，而减少了传统模式下将网卡内存由内核态拷贝到用户态的开销
* 用户态驱动通过轮询读取数据包，减少了原本中断的开销



* [注]：DPDK的mmap的应用程序将虚拟地址映射到一块用户空间的物理内存（也就是为网卡分配的内存），而非传统的内核空间的物理内存