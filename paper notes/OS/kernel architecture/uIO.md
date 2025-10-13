# uIO

## Overview

<img src="..\..\assets\image-20251002015435568.png" alt="image-20251002015435568" style="zoom:42%;" />

* 主机端uIO进程：管理console、FS Image（位于宿主机上的文件系统镜像，包含 Unikernel 能够访问到的文件和程序）
* uIO context：一个线程，与主应用程序共享地址空间，在 Unikernel 的整个运行期间是一直存在的

**主要流程**

* uIO将其 console 和 FS image 分别连接到 unikernel 的 communication layer 的 Console driver 和 FS driver
* 用户向控制台发送命令，控制台通过 Console driver 将命令发送给 uIO context
* uIO context 处理命令，动态地通过文件系统加载程序，并调用它
  * 加载：
    * uIO context 从 FS image 中读取这个外部程序的文件
    * 解析这个文件的头部信息，找到其中的代码段 (`.text`) 和数据段 (`.data`)
    * 在 Unikernel 的内存中申请一块可执行的内存空间，并将文件的代码段和数据段加载进去
  * 重定位：
    * 加载进来的外部程序可能需要调用 Unikernel 内部已经存在的函数
    * 在 Unikernel 的符号表中查找所需符号（如 `printf`）的真实地址
    * 将其回填到加载到内存的代码的正确位置上

* 程序在uIO上下文中执行，并与主应用程序隔离

## Design

### uIO Interfaces

* 主机端 uIO 进程 ←→ unikernel 内组件

  * 通信协议：VirtIO

* unikernel底层 ←→ unikernel 内组件

  * 通信方式：APIs

    <img src="..\..\assets\image-20251002024924718.png" alt="image-20251002024924718" style="zoom:50%;" />

