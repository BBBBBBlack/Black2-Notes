# Kprobe

[kprobes](https://sourcegraph.com/github.com/torvalds/linux/-/blob/Documentation/trace/kprobes.rst)

Linux 内核的**动态调试工具**，允许在不中断内核运行的情况下：

- **插入断点**：拦截任意内核函数。
- **收集信息**：获取调试数据或性能指标。
- **灵活控制**：支持前置（`pre_handler`）和后置（`post_handler`）处理。

## 流程

<img src="..\..\..\assets\e3f8bea8721e31df3e7ea45a46013dbf.png" alt="在这里插入图片描述" style="zoom:90%;" />

<img src="..\..\..\assets\下载.png" alt="下载" style="zoom:40%;" />

1. **指令替换**：

   将目标指令的首字节替换为断点指令（如 `int3`）

2. **触发trap**：

   CPU 执行到断点时触发trap，保存寄存器状态（[如何在程序运行时动态修改指令？](..\..\..\..\Operate System\source code\text_poke.md)）

3. **执行处理器**：

   依次调用 `pre_handler`→ 单步执行原指令 → `post_handler`

4. **恢复执行**：

   继续执行原代码流
