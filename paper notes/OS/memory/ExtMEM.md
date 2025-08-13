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

  * 使用信号处理路径signing handling将错误转发给用户态程序——Linux仿造exokernel的upcall机制
  
    ```c
    // 理想的纯upcall（如Exokernel）
    void kernel_page_fault_handler(unsigned long fault_addr) {
        // 直接修改用户态执行上下文
        current->regs.ip = user_fault_handler;
        current->regs.di = fault_addr;  // 传递参数
        // 返回用户态时直接执行handler
    }
    ```
  
    <img src="..\..\assets\image-20250807031452975.png" alt="image-20250807031452975" style="zoom:55%;" />
  
    * 应用程序向内核注册一个内存区域并注册upcall handler
  
    * faulting thread触发page fault，由用户态切换至内核态
  
    * 内核调用了 `handle_userfault` 交给 userfaultfd 相关的代码进行处理，向引发 该page fault 的faulting thread发送一个 SIGBUS 信号
  
    * 内核在faulting thread设置新的执行上下文
  
      ```c
      // 内核内部操作（简化表示）
      void kernel_setup_upcall_context(struct task_struct *task, void (*handler)()) {
          struct pt_regs *regs = task_pt_regs(task);
          
          // 在用户栈上保存当前状态
          unsigned long sp = regs->sp - sizeof(struct sigframe);
          struct sigframe *frame = (struct sigframe *)sp;
          
          // 保存原始执行状态
          frame->original_ip = regs->ip;     // 保存出错的指令地址
          frame->original_sp = regs->sp;     // 保存原始栈指针  
          frame->original_regs = *regs;      // 保存所有寄存器
          
          // 设置新的执行上下文
          regs->ip = (unsigned long)handler; // 指令指针指向处理函数
          regs->sp = sp;                     // 更新栈指针
          regs->di = fault_address;          // 第一个参数：出错地址
          
          // 当线程返回用户态时，会从handler函数开始执行
      }
      ```
  
    * faulting thread返回用户空间，跳到一开始注册的upcall handler执行，upcall handler调用policy layer的方法，采取不同的内存策略
  
    * faulting thread从handler得到新的页面
  
    * 继续执行

## Observability Layer

跟踪内存访问，以区分经常访问（热）和不常访问（冷）数据

* page fault的故障地址
* MMU访问和脏位
* 硬件计数器

## Policy Layer

Core Layer的handler调用，能够自定义策略：识别需要驱逐或降级的冷页，并选择潜在的页面进行预取或promotion