# Design

EXTMEM被设计为一个动态链接库，可以通过[LD_PRELOAD](../../../Operate System/base/LD_PRELOAD.md)透明地加载到应用程序地址空间中

用户代码与EXTMEM交互：

* 通过库API显式交互
* 通过系统调用隐式交互：当用户代码调用`mmap`时，EXEMEM用**Intel libsyscall_intercept**拦截，接管并执行它自己定义的功能（系统调用、EXTMEM 库中的其他功能）

## Core Layer

负责与内核交互

EXEMEM管理其绑定的应用程序在本地和远程（如NVMe SSD）上的后端存储资源，当多个EXEMEM实例共享一块内存时，由global manger为每个EXEMEM实例（即一个被管理的应用程序）分配一块内存，由EXTMEM对这块内存进行细粒度的管理

* EXEMEM拦截用户代码的`mmap`等系统调用（在进程的**虚拟地址空间**中预留了一段连续的地址范围，**但没有为它分配任何实际的物理内存** ）

* 将应用程序用到的内存区域注册/注销到userfaultfd

  ```c
  struct uffdio_register uffdio_register;
  uffdio_register.range.start = (uint64_t)p;
  uffdio_register.range.len = length;
  uffdio_register.mode = UFFDIO_REGISTER_MODE_MISSING | UFFDIO_REGISTER_MODE_WP;
  if (ioctl(uffd, UFFDIO_REGISTER, &uffdio_register) == -1) {
      // ... error handling
  }
  ```

* 当出现page fault时（当虚拟地址无法转换为物理地址，就会立刻触发一个**缺页异常 (Page Fault)**），userfaultfd将错误转发给EXTMEM处理

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

    **弊端：**（IPC开销大、多个handler thread必须在fd和 faulting thread的等待队列上同步，效率低——）

    <img src="..\..\assets\flow.png" alt="img" style="zoom:50%;" />
  
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
  
      ```c
      void uswap_register_handler(int sig)
      {
          struct sigaction action;
          LOG("Registering a signal handler\n");
      
          action.sa_flags = SA_RESTART;
          action.sa_handler = NULL;
          // 当指定的信号发生时，请调用 uswap_sig_handler
          action.sa_sigaction = uswap_sig_handler;
          action.sa_flags |= SA_SIGINFO;
          sigemptyset(&action.sa_mask);
          // 将配置好的 action 结构体与指定的信号 sig 关联起来
          int ret = sigaction(sig, &action, NULL);
          if (ret != 0)
          {
              perror("sigaction failed \n");
              
          }
      
          LOG("Signal handler for signal %d registered\n", sig);
      }
      ```
    
    * faulting thread触发page fault，由用户态切换至内核态
    
    * 内核调用了 `handle_userfault` 交给 userfaultfd 相关的代码进行处理，向引发该page fault 的faulting thread的私有待处理队列发送一个 SIGBUS 信号
    
    * 当faulting thread即将从内核态返回用户态时，读取待处理队列中的SIGBUS信号
    
    * 调用`handle_signal`函数，构建信号帧 (`setup_rt_frame`)
    
      * 在故障线程的**用户态栈**上创建一个包含完整寄存器上下文和 `siginfo_t` 信息的**信号帧**
    
      * 修改保存在内核中的返回上下文
    
      * 将返回地址（`regs->ip`）修改为 `upcall handler` 的地址，并将栈指针（`regs->sp`）指向刚刚创建的信号帧
    
    
      ```c
      static int __setup_rt_frame(int sig, struct ksignal *ksig,
      			    sigset_t *set, struct pt_regs *regs)
      {
      	struct rt_sigframe __user *frame;
      	void __user *restorer;
      	void __user *fp = NULL;
      
          // 在当前线程的用户态栈上计算出一个安全的位置，用来存放即将创建的“信号帧”
      	frame = get_sigframe(&ksig->ka, regs, sizeof(*frame), &fp);
      
      	if (!user_access_begin(frame, sizeof(*frame)))
      		return -EFAULT;
      
      	unsafe_put_user(sig, &frame->sig, Efault);
      	unsafe_put_user(&frame->info, &frame->pinfo, Efault);
      	unsafe_put_user(&frame->uc, &frame->puc, Efault);
      
      	/* Create the ucontext.  */
      	if (static_cpu_has(X86_FEATURE_XSAVE))
      		unsafe_put_user(UC_FP_XSTATE, &frame->uc.uc_flags, Efault);
      	else
      		unsafe_put_user(0, &frame->uc.uc_flags, Efault);
      	unsafe_put_user(0, &frame->uc.uc_link, Efault);
      	unsafe_save_altstack(&frame->uc.uc_stack, regs->sp, Efault);
      
      	/* Set up to return from userspace.  */
      	restorer = current->mm->context.vdso +
      		vdso_image_32.sym___kernel_rt_sigreturn;
      	if (ksig->ka.sa.sa_flags & SA_RESTORER)
      		restorer = ksig->ka.sa.sa_restorer;
      	unsafe_put_user(restorer, &frame->pretcode, Efault);
      
      	/*
      	 * This is movl $__NR_rt_sigreturn, %ax ; int $0x80
      	 *
      	 * WE DO NOT USE IT ANY MORE! It's only left here for historical
      	 * reasons and because gdb uses it as a signature to notice
      	 * signal handler stack frames.
      	 */
          // 将完整的上下文信息（包括所有寄存器的值、siginfo_t 等）拷贝到刚刚计算出的用户态栈地址上
      	unsafe_put_user(*((u64 *)&rt_retcode), (u64 *)frame->retcode, Efault);
      	unsafe_put_sigcontext(&frame->uc.uc_mcontext, fp, regs, set, Efault);
      	unsafe_put_sigmask(set, frame, Efault);
      	user_access_end();
      	
      	if (copy_siginfo_to_user(&frame->info, &ksig->info))
      		return -EFAULT;
      
      	/* Set up registers for signal handler */
          // 将栈顶指针，指向刚刚在用户态栈上创建的那个信号帧！！！！！！！！！！！
      	regs->sp = (unsigned long)frame;
          // 将下一条要执行的指令地址，强行设置为信号处理函数的地址！！！！！！！！
      	regs->ip = (unsigned long)ksig->ka.sa.sa_handler;
      	regs->ax = (unsigned long)sig;
      	regs->dx = (unsigned long)&frame->info;
      	regs->cx = (unsigned long)&frame->uc;
      
      	regs->ds = __USER_DS;
      	regs->es = __USER_DS;
      	regs->ss = __USER_DS;
      	regs->cs = __USER_CS;
      
      	return 0;
      Efault:
      	user_access_end();
      	return -EFAULT;
      }
      ```
    
    * faulting thread返回用户空间，跳到一开始注册的upcall handler执行，upcall handler调用policy layer的方法，采取不同的内存策略
    
      ```c
      //
      void uswap_sig_handler(int code, siginfo_t *siginfo, void *context)
      {
          // ...
          // 从 siginfo 结构体中获取缺页的内存地址
          fault_addr = (uint64_t)siginfo->si_addr;
          // ...
      
          page = find_page(page_boundry);
      
          // 根据页面的状态，分发给不同的处理函数
          if(page == NULL){ // 第一次访问
              handle_first_fault(page_boundry);
          }
          else if(page->swapped_out == true){ // 页面被换出
              handle_missing_fault(page);
          }
          else{  // 写保护缺页
              handle_wp_fault(page);
          }
          // ...
      }
      ```
    
    * faulting thread从handler得到新的页面
    
    * 继续执行

## Observability Layer

跟踪内存访问，以区分经常访问（热）和不常访问（冷）数据

* page fault的故障地址

* MMU访问位和脏位

  ```c
  uint64_t pt_get_bits(struct user_page *page)
  {
    uint64_t ret;
    struct uffdio_page_flags page_flags;
  
    page_flags.va = page->va;
    assert(page_flags.va % PAGE_SIZE == 0);
    page_flags.flag1 = PT_ACCESSED_FLAG;
    page_flags.flag2 = PT_DIRTY_FLAG;
  
    if (ret = ioctl(uffd, UFFDIO_GET_FLAG, &page_flags) < 0) {
      fprintf(stderr, "userfaultfd_get_flag returned < 0\n");
      assert(0);
    }
    ret = page_flags.res1 | page_flags.res2;
    
    return ret;
  }
  ```

* 硬件计数器****

## Policy Layer

Core Layer的handler调用，能够自定义策略：识别需要驱逐或降级的冷页，并选择潜在的页面进行预取或promotion

[ExtMem/src at master · SepehrDV2/ExtMem](https://github.com/SepehrDV2/ExtMem/tree/master/src)

* upcall原本的实现
* EXTMEM版upcall比IPC好在哪里
* 