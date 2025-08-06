# Design

EXTMEM被设计为一个动态链接库，可以通过LD_PRELOAD透明地加载到应用程序地址空间中

用户代码与EXTMEM交互：

* 通过库API显式交互
* 通过系统调用隐式交互：当用户代码调用`mmap`时，EXEMEM用Intel libsyscall_intercept拦截，接管并执行它自己定义的功能（系统调用、EXTMEM 库中的其他功能）

## Core Layer

负责与内核交互

EXEMEM管理其绑定的应用程序在本地和远程（如NVMe SSD）上的后端存储资源，当多个EXEMEM实例共享一块内存时，由global manger为每个EXEMEM分配

* EXEMEM拦截用户代码的`mmap`等系统调用

* 将应用程序用到的内存区域注册/注销到userfaultfd

* 当出现page fault时，userfaultfd将错误转发给EXTMEM处理

  * 使用进程间通信（IPC）将错误转发给用户态程序——Linux

    <img src="..\..\assets\image-20250806231205140.png" alt="image-20250806231205140" style="zoom:70%;" />

    * 应用程序向内核注册一个内存区域并接收一个**文件描述符fd**
    * 处理线程Handler thread（处理故障的线程）调用 select/poll监听fd
    * faulting thread触发page fault，由用户态切换至内核态
    * 内核调用了 `handle_userfault` 交给 userfaultfd 相关的代码进行处理。一个待处理的消息 `uffd_msg` 结构通过该 fd 发送到handler thread，faulting thread被挂起进入阻塞状态
    * handler thread接收待处理消息，通过 ioctl 处理page fault：
      * `UFFDIO_COPY`：将用户自定义数据拷贝到 faulting page 上
      * `UFFDIO_ZEROPAGE` ：将 faulting page 置 0
      * `UFFDIO_WAKE`：用于配合上面两项中 `UFFDIO_COPY_MODE_DONTWAKE` 和 `UFFDIO_ZEROPAGE_MODE_DONTWAKE` 模式实现批量填充
    * 在处理结束后handler thread发送信号唤醒 faulting thread继续工作

    （IPC开销大、多个handler thread必须在fd和 faulting thread的等待队列上同步，效率低）

  * 2