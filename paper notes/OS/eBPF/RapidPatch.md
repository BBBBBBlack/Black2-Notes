# RapidPatch

## Overview

<img src="..\..\assets\image-20250916030823977.png" alt="image-20250916030823977" style="zoom:80%;" />

## Development

生成 eBPF Source Patch 和 eBPF Patch Configuration

**original C source code patch**

标准的、官方的漏洞修复方案

* 针对有漏洞的源程序，在其上通过增减代码进行修复

* 使用**`diff`** 工具比较新旧文件，生成一个标准的`.patch`补丁文件，命令如下
  ```shell
  diff -u main_v1.c main_v2.c > buffer_overflow_fix.patch
  ```

  生成文件如下：

  ```sh
  --- main_v1.c   2025-09-15 00:55:10.000000000 +0530
  +++ main_v2.c   2025-09-15 00:55:50.000000000 +0530
  @@ -6,9 +6,13 @@
       char buffer[128];
       printf("Processing %d bytes of data...\n", len);
   
  -    // 漏洞所在：没有检查len是否大于128
  +    // 修复：增加了长度检查
  +    if (len > sizeof(buffer)) {
  +        fprintf(stderr, "Error: Input data is too large!\n");
  +        return; // 拒绝处理过长数据
  +    }
       memcpy(buffer, data, len);
   
       // ... 后续处理 ...
  ```

* 使用 `patch` 命令应用补丁，命令如下
  ```
  patch -p1 < ../xxx.patch
  ```

  该命令读取补丁文件中的指令，并自动修改本地的源代码文件

* 源代码被更新后，**重新编译**整个软件，生成新的二进制可执行文件，用其替换正在运行的、有漏洞的旧版本

**development部分将origin C source patch修改为 eBPF source code patch**，以实现无需重新编译即可修复漏洞的热补丁技术

### Filter Patch

在漏洞代码段的入口处过滤掉恶意或非法输入

* 通过stack_frame将C程序的栈信息传递给eBPF
* eBPF通过修改返回地址来重定向控制流

<img src="..\..\assets\image-20250916032437428.png" alt="image-20250916032437428" style="zoom:45%;" />

### Code Replace Patch

eBPF 补丁代码替换漏洞函数来修复它

* 通过helper function实现FFI，以便eBPF程序可以调用固件的原生C代码
* eBPF通过修改返回地址将控制流重定向到漏洞函数的退出点

<img src="..\..\assets\image-20250916033436156.png" alt="image-20250916033436156" style="zoom:46%;" />

### eBPF Patch Configuration

关于补丁编译和补丁部署的关键信息

**variable_map——eBPF中的宏：固件中的C代码符号；本机 C 函数和所需全局变量的映射（后面会用到！！！）**

<img src="..\..\assets\image-20250916033933056.png" alt="image-20250916033933056" style="zoom:36%;" />

## Generation

建立eBPF补丁与固件的连接——调用原生C程序的函数、访问其全局变量

eBPF patch中所有引用函数名称和全局变量的宏都被替换为**具体的固件地址**

输入：eBPF Source Patch、eBPF Patch Configuration、Firmware Symbol File

* 遍历**eBPF Patch Configuration**中variable_map，为**eBPF Source Patch**中声明的宏 找到其在固件C程序中对应的符号
* 在**Firmware Symbol File**中找到对应符号的具体地址



获取Patch Install Address

* 查找**eBPF Patch Configuration**中的install_point配置项，找到目标函数的名字
* 在**Firmware Symbol File**中找到目标函数的具体地址

## Verification

离线验证

若补丁被识别为安全，则可以直接在设备上部署；若补丁被报告为不安全，必须执行进一步的人工测试

## Deployment & Execution

<img src="..\..\assets\image-20250916102610300.png" alt="image-20250916102610300" style="zoom:40%;" />

### Patch Install

执行即时编译（JIT），生成 eBPF patch字节码，将其保存至Patch List

### Patch Trigger

<img src="..\..\assets\image-20250916102955251.png" alt="image-20250916102955251" style="zoom:30%;" />

Kprobe、FPB：由hardware breakpoint触发，在系统运行时任意地址插入或移除

Fixed Patch Points：在编程或编译固件时添加，只能放置在函数的固定位置

### Patch Loader

<img src="..\..\assets\image-20250916104351365.png" alt="image-20250916104351365" style="zoom:40%;" />

* 当补丁被触发时，保存当前函数上下文
* 调用_patch_dispatch() 函数，根据index（lr value）在Patch List中定位patch
* 在patch完成并退出后，通过修改lr（返回地址）寄存器，根据eBPF虚拟机的返回代码重定向控制流

### Patch Execution and Runtime Protection