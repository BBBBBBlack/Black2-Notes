# Userfaultfd

<img src=".\assets\flow.png" alt="img" style="zoom:65%;" />

* faulting 线程读取了一块未分配物理页的内存，触发了page fault
* 此时进到内核中进行处理，内核调用了 `handle_userfault` 交给 userfaultfd 相关的代码进行处理
* 此时该线程将被挂起进入阻塞状态
* 同时一个待处理的消息 `uffd_msg` 结构通过该 fd 发送到了另一个 monitor 线程
* monitor线程可以调用相关 API 进行处理 （ `UFFDIO_COPY` 或 `UFFDIO_ZEROPAGE`）并告知内核唤醒 faulting 线程

## 使用

分配一个userfaultfd，检查API

```c
 /* Create and enable userfaultfd object */

uffd = syscall(__NR_userfaultfd, O_CLOEXEC | O_NONBLOCK);
if (uffd == -1)
   errExit("userfaultfd");

uffdio_api.api = UFFD_API;
uffdio_api.features = 0;
// 内核验证其是否支持用户程序请求的 API 版本和所有 features
if (ioctl(uffd, UFFDIO_API, &uffdio_api) == -1)
   errExit("ioctl-UFFDIO_API");
```

注册需要进行 userfault 的内存区域

```c
/* Register the memory range of the mapping we just created for
          handling by the userfaultfd object. In mode, we request to track
          missing pages (i.e., pages that have not yet been faulted in). */

uffdio_register.range.start = (unsigned long) addr;
uffdio_register.range.len = len;
uffdio_register.mode = UFFDIO_REGISTER_MODE_MISSING;
if (ioctl(uffd, UFFDIO_REGISTER, &uffdio_register) == -1)
   errExit("ioctl-UFFDIO_REGISTER");
```

创建monitor线程，监听fd事件——读取uffd_msg

```c
for (;;) {

   /* See what poll() tells us about the userfaultfd */

   struct pollfd pollfd;
   int nready;
   pollfd.fd = uffd;
   pollfd.events = POLLIN;
   // 阻塞等待
   nready = poll(&pollfd, 1, -1);
   if (nready == -1)
       errExit("poll");

   /* Read an event from the userfaultfd */
   nread = read(uffd, &msg, sizeof(msg));
   if (nread == 0) {
       printf("EOF on userfaultfd!\n");
       exit(EXIT_FAILURE);
   }

   if (nread == -1)
       errExit("read");
```

## 源码

