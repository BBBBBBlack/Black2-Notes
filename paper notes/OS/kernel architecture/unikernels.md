## 设备结构

### 配置与部署

将数据库、Web服务器等视为库（Library），而非独立的应用程序

- **静态参数**：通过构建工具（如Makefile）在编译时固化（如监听端口）。
- **动态参数**：运行时通过API调用调整（如动态加载证书）。

### 紧凑性与优化

将OS功能（如设备驱动、协议栈）作为库（libraries）直接链接到应用中，编译时仅包含必要的代码

* 配置文件静态评估：在编译阶段解析配置文件，将其内容嵌入代码

* whole-system optimization techniques（全系统优化技术）：通过编译时裁剪（如死代码消除）减少冗余代码

​		——未调用的库代码会被编译器完全剔除，以生成极简的二进制文件（KB~MB级），显著减少内存和存储占用。应用程序和所有库代码运行在**同一地址空间**，无进程隔离，通过语言或编译器的安全特性（如 Rust 的所有权模型）避免冲突

### 安全性

* 如何认证与其通信的外部系统或用户的身份？

  传统的OS：multi-user access control mechanism（多用户访问控制机制）

  ​	当进程尝试访问资源（如打开文件）时，内核按以下顺序检查：

  1. **进程身份**：检查进程的 UID/GID。
  2. **文件权限**：匹配 `owner/group/others` 的 `rwx` 位。
  3. **特殊权限**：检查 SUID/SGID 或 Capabilities。
  4. **安全模块**：SELinux/AppArmor 策略进一步限制。

  unikernels：单进程、单用户，外部实体通过 SSL/TLS 证书或 SSH 公钥验证

#### 编译时裁剪和静态配置

传统OS面临问题：

* 向后兼容性 → 代码臃肿：代码越多，潜在漏洞越多（如 OpenSSL 的 Heartbleed）
* 动态配置 → 错误配置风险：数据泄露、远程代码执行（如 CVE-2017-7494）

unikernels解决：

* 显式配置：只有配置文件中明确引用的模块才会在输出中链接
* 静态验证：通过模块依赖关系图，只保留所需的服务

#### 普及的类型安全

放弃源码向后兼容性，使用类型安全的语言彻底重构系统

* 隔离：

  Hypervisor 替代进程隔离

  - 传统 OS：
    进程间通过内核机制（如 `fork()`、`pipe()`）隔离和通信。

  - unikernels：

    每个组件运行在独立的 VM 中，通过 Hypervisor（如 Xen/KVM）隔离

* 通信：

  * 同一 unikernels 内的通信：函数调用，无进程间通信
  * 跨  unikernels  实例的通信：标准网络协议（如 HTTP/2、gRPC）
  * 与非 unikernels 系统的通信：消息传递

#### 密封和VM权限删除

* 密封：

  确保单个 Unikernel **内部**运行时不可篡改（防止代码注入攻击）

  * 在 Unikernel 启动初始化阶段，建立一组页表，确保没有任何内存页同时具有可写（Writable）和可执行（Executable）权限——W^X（Write XOR Execute）
  * 通过 `seal` 超调用（hypercall） 通知 Hypervisor 锁定页表，禁止后续修改（如通过 `mprotect` 动态调整权限）

#### 编译时地址随机化

传统操作系统（如Linux）：在运行时通过动态调整内存布局（如栈、堆、库的加载地址）来增加攻击者预测内存结构的难度，从而防范缓冲区溢出等攻击

Unikernel ：在编译阶段通过生成随机化的链接脚本（linker script）实现ASR



## Mirage Unikernels

每个Mirage Unikernel 都使用单个虚拟CPU在Xen上运行

### PVBoot Library

初始化VM：分配单个虚拟 CPU、初始化 Xen 事件通道，并跳转到入口函数，为程序分配一个统一的 64 位地址空间

* **Slab 分配器**：用于支持运行时中的 C 代码部分，但由于大部分代码为 OCaml 实现，其使用频率较低。
* **Extent 分配器**：保留连续的虚拟内存区域，并以 2MB 为单位管理，支持映射 x86-64 架构的大页（superpages）

该VM会休眠，直到I/O可用或超时

### Language Runtime

#### 内存管理

**OCaml 垃圾回收器（GC）** 被保留，并适配 unikernel 的地址空间模型；

64位地址空间布局：

<img src="..\..\assets\image-20250604045337795.png" alt="image-20250604045337795" style="zoom:50%;" />

- Text/Data 区：OCaml runtime + 应用——编译后生成的代码（函数体）和**静态数据**（全局常量、模块初始值等）
- Heap 区：用于 GC 的 minor/major heap——程序运行过程中**动态分配**的值（如 list、tuple、对象、字符串等），由 GC 管理
  - **Minor Heap（小对象堆）**：用于短命对象，单个 2MB 的块，按 4KB 增长；
  - **Major Heap（大对象堆）**：用于长寿命对象，使用 2MB 的 superpage 分配，性能高；
- I/O Page 区——具体见设备驱动程序部分
  - 用于设备通信的**共享页**（减少 GC 扫描负担）；
  - PVBoot从该区域分配外部内存页，并在minor heap中分配一个小的代理值。Mirage提供了一个库来引用OCaml中的数据，而不需要数据副本

#### 并发机制

使用了 **Lwt 协程库** 来构建非阻塞 I/O —— 把传统会阻塞的操作（domainpoll）包装成可以等待的事件——返回事件描述符，而非阻塞VM

```ocaml
(* echo.ml *)
open Lwt.Infix
open Mirage_types_lwt

module Main (S: STACKV4) = struct

  module U = S.UDPV4

  let start stack =
    let udp = S.udpv4 stack in
    let port = 1234 in

    (* 绑定端口并监听数据 *)
    (* 当有 UDP 数据包到达指定端口（1234）时，会自动调用你写的处理逻辑 *)
    U.listen udp ~port (fun ~src ~dst ~src_port buf ->
      let msg = Cstruct.to_string buf in
      Logs.info (fun f -> f "Received from %a:%d - %s"
                   Ipaddr.V4.pp_hum src src_port msg);
      (* 直接原样回传 *)
      U.write ~src:dst ~dst:src ~dst_port:src_port udp buf |> ignore
    );

    (* 无限挂起等待事件，主线程不会退出 *)
    (* Lwt.pause ()：让出CPU给其他协程运行——domain在监听UDP数据包到达的事件，若事件发生，唤起相应的协程处理该事件 *)
    (* 当Lwt.pause()完成后，再调用 wait_forever() *)
    let rec wait_forever () = Lwt.pause () >>= wait_forever in
    wait_forever ()
end

```

整体流程：

```
+------------------+            UDP 报文到达            +----------------------+
|   wait_forever   |  <-------------------------------- |     Xen 网络驱动     |
|  (Lwt.pause...)  |                                     +----------------------+
|    挂起线程      |                                     ↑
+------------------+                            事件通知（event channel）
         ↓                                          ↑
     Lwt 恢复调度器                         Mirage domainpoll 监听
         ↓                                          ↑
+------------------+                         +--------------------+
|  U.listen 回调函数 | ←-------------------- |     Mirage 网络栈   |
|   （你写的逻辑）  |                         +--------------------+
+------------------+
```



```
       主程序
+------------------+        UDP 报文到达   +-------------+
|   wait_forever   |  <------------------ |   网络驱动   |
|  (Lwt.pause...)  |                      +-------------+
|    挂起线程      |                              ↑
+------------------+                   事件通知（event channel）
         ↓                                       ↑
    Lwt 创建协程执行                         domainpoll 监听
         ↓                                       ↑
+------------------+                      +------------+
|  U.listen 回调函数 |  <------------------ |   网络栈   |
|   （自定义逻辑）    |                      +- ----------+
+------------------+
```



### 设备驱动程序

Xen设备结构：

**frontend driver**：运行在 Mirage（即 guest VM）中

**backend driver**：运行在 Xen dom0（或其他特权域）中，直接接触硬件——将前端请求多路复用到真实的物理设备

* 通信方式：

  * **event channel**：类似虚拟中断，用于发通知；

  * **shared memory page**：用于传递数据；被划分为多个大小固定的请求槽，由**producer/consumer 指针**追踪：协调前后端对 ring 中数据的写入和读取。frontend写入请求读取响应，backend读取请求写入响应，响应和请求在一个请求槽中

    * 实现细节：

      OCaml 的整数不是裸值，而是对象（boxed），故若要将值写入共享内存，需先在堆中分配一个对象，再拷贝进共享内存，效率低

      解决方法：Bigarray 模块——将外部分配的内存安全地封装为 OCaml 堆上的数组

      通过 OCaml 的语法扩展（camlp4）实现了 `cstruct`，生成一些访问函数，供直接操作外部内存数组

      ```
      Xen 提供的共享页（外部内存）
              ↓
         映射为 Bigarray.t   ← OCaml 内建模块，支持对外部内存的数组访问
              ↓
         封装为 Cstruct.t     ← cstruct 库：对 Bigarray 的包装 + 结构体访问器
              ↓
       提供结构化字段访问接口，如 get_ipv4_src(), get_tcp_seq()
      ```

    Xen 的设备协议并不直接将数据写入共享内存页（shared ring），而是用它来协调传递 4KB 大小内存页的**引用**

    两个通信的虚拟机共享一个**grant table（授权表）**，它将物理内存页映射为一个整数索引（称为 grant）

    * VM1将某一内存页的索引送入共享内存 >> 通过 event channel 通知 Dom0 的 backend driver有新数据可处理

      （将该内存页授权给backend driver）

    * backend driver通过索引定位到该内存页，读取其内容，并通过物理网卡（或桥接设备）发送出去

    * VM2通过自己这边的共享内存定位到接收到的消息所在内存页，读取内容



| 运行环境        | 是否推荐   | 是否体现 unikernel 优势 | 说明                                            |
| --------------- | ---------- | ----------------------- | ----------------------------------------------- |
| **Xen (PVHv2)** | ✅ 强烈推荐 | ✅✅✅                     | MirageOS 默认后端，论文实验主环境               |
| **Solo5-hvt**   | ✅ 推荐     | ✅✅                      | 类似 Xen 的隔离和高性能                         |
| **virtio**      | ✅ 推荐     | ✅✅                      | 可运行于主流云平台如 GCP                        |
| **Solo5-spt**   | ⚠️ 有限推荐 | ❌ 部分                  | 沙箱隔离不如 hypervisor，限制多                 |
| **unix/macOS**  | ❌ 不推荐   | ❌                       | 无隔离，不能体现 unikernel 本质，仅用于开发调试 |