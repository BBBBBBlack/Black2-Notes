### eBPF调用uprobe

uprobe：用户态函数的探针

* 当用户态函数（如 `malloc`）被 uprobe 挂载时，内核将其首条指令替换为 `int3` 断点指令（x86）或类似陷阱指令（ARM）
* 用户进程执行到被探测的指令时，CPU 触发断点异常，陷入内核。
* 内核将 uprobe 事件传递给 eBPF 子系统处理
* eBPF程序执行完后返回用户态继续执行

——两次上下文切换，开销大

<img src="..\..\..\assets\image-20250729190532219.png" alt="image-20250729190532219" style="zoom:81%;" />

### bpftime调用uprobe

不需要上下文切换，开销小

<img src="..\..\..\assets\image-20250729192542072.png" alt="image-20250729192542072" style="zoom:90%;" />

两个库：

* bpftime-syscall.so：将与eBPF相关的系统调用转换为用户态函数调用；创建共享内存，将bpf程序放置其中
* bpftime-agent.so：以共享库的形式体现，可以动态注入到目标运行进程中；加载 bpftime 程序，后恢复用户态程序执行

过程：

* eBPF程序启动，bpftime-syscall.so将其加载到共享内存

* ptrace暂停target process，bpftime-agent.so 共享库被注入目标进程，读取共享内存中的 eBPF 程序，将字节码编译为原生指令

* 当事件被触发，拦截的指令跳转到 bpftime 程序，bpftime执行、更新共享内存

  