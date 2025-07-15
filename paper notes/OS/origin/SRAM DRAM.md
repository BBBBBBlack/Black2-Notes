![img](https://static.mianbaoban-assets.eet-china.com/xinyu-images/MBXY-CR-7e46e1776c336e7a09c1e72d87cc9799.png)

[原文](https://www.cnblogs.com/wwj99/p/12842859.html#%E7%BC%93%E5%AD%98%E4%B8%80%E8%87%B4%E6%80%A7%E9%97%AE%E9%A2%98)

<img src="..\..\assets\1896043-20200505151920103-1066177139.png" alt="img" style="zoom:60%;" />

<img src="..\..\assets\6878ac7c6f1f33d637591c6a1aad0159.png" alt="在这里插入图片描述" style="zoom:80%;" />

## SRAM：

### CPU Cache：

L1 的 Cache 往往就嵌在 CPU 核心的内部

L2 的 Cache 同样是每个 CPU 核心都有的，不过它往往不在 CPU 核心的内部

L3 Cache，则通常是多个 CPU 核心共用的，尺寸会更大一些

CPU Cache从Memory中读取数据，每次读取一个Cache Line（通常为64个字节）

映射：见组原笔记

**volatile关键字：**确保对其修饰的变量的读取和写入都一定同步到主存里而非Cache中

```java
public class VolatileTest {
    private static volatile int COUNTER = 0;
 
    public static void main(String[] args) {
        new ChangeListener().start();
        new ChangeMaker().start();
    }
 
    static class ChangeListener extends Thread {
        @Override
        public void run() {
            int threadValue = COUNTER;
            while ( threadValue < 5){
                if( threadValue!= COUNTER){
                    System.out.println("Got Change for COUNTER : " + COUNTER + "");
                    threadValue= COUNTER;
                }
            }
        }
    }
 
    static class ChangeMaker extends Thread{
        @Override
        public void run() {
            int threadValue = COUNTER;
            while (COUNTER <5){
                System.out.println("Incrementing COUNTER to : " + (threadValue+1) + "");
                COUNTER = ++threadValue;
                try {
                    Thread.sleep(500);
                } catch (InterruptedException e) { e.printStackTrace(); }
            }
        }
    }
}

```

输出：

```
Incrementing COUNTER to : 1
Got Change for COUNTER : 1
Incrementing COUNTER to : 2
Got Change for COUNTER : 2
Incrementing COUNTER to : 3
Got Change for COUNTER : 3
Incrementing COUNTER to : 4
Got Change for COUNTER : 4
Incrementing COUNTER to : 5
Got Change for COUNTER : 5
```

去掉volatile后：

Listener从Cache中获取COUNTER，无法获取Maker写入主存中的变化

```
Incrementing COUNTER to : 1
Incrementing COUNTER to : 2
Incrementing COUNTER to : 3
Incrementing COUNTER to : 4
Incrementing COUNTER to : 5
```

在Listener的循环中每次sleep 500ms：

恢复——Listener有时间从主存同步Maker修改的数据

### 写入策略：

写直达

<img src="..\..\assets\1896043-20200505155916725-1428902902.jpg" alt="img" style="zoom:25%;" />

写回

<img src="D:\xxx\Black2\Paper notes\assets\1896043-20200505155918831-1892190582.jpg" alt="img" style="zoom:20%;" />

### MESI协议

缓存一致性问题：在写回策略中，CPU01将数据写入Cache Block但还未同步到主存，CPU02将数据从主存中读出，无法读到最新的数据

解决：

1. 写传播：一个CPU的数据更新，要传播到其他CPU的Cache里，一种实现——**总线嗅探**（把所有的读写请求都通过总线（Bus）广播给所有的 CPU 核心，然后让各个核心去“嗅探”这些请求，并根据本地的情况进行响应）
2. 事务串行化：在一个 CPU 核心里面的读取和写入，在其他的节点看起来，顺序是一样的

MESI——总线嗅探的一种协议：

**M : modified** —— 修改，数据只存在于本Cache中，但被本核心修改，还没同步到内存
**E : exclusive** —— 独享，数据只存在于本Cache中，和内存数据一样
**S : shared** —— 共享，数据存在于很多Cache中，和内存数据一样
**I : invalid** ——无效，本核心Cache line无效

<img src="..\..\assets\1896043-20200506145053802-1415348716.jpg" alt="img" style="zoom:25%;" />

核心A有一份和内存一致的数据X，其他核心均没有，此时X的状态为E——独占

核心A修改了这份数据，但还没有传回内存，此时X的状态为M——修改

核心B通过总线告知自己需要获取数据X，总线向各核心索取X的最新数据

核心A将数据X传回总线，核心B和主内存都从总线读取最新的数据X，然后A、B核心的缓存块状态为S——共享

核心B对自己缓存中的数据X修改，B核心缓存块为M——修改，同时将该消息告知总线，A核心缓存为I——无效

## DRAM：

<img src="..\..\assets\image-20241227075847326.png" alt="image-20241227075847326" style="zoom:35%;" />

* Z线：

  * 1——T5、T6导通，读写操作
  * 0——T5、T6断开，位线与内部线路脱离，信号保持状态

* 写入：

  * W—1，~W—0 ----> A—0，B—1 ---> T2—截止，T1导通，写入0

  * W—0，~W—1 ----> A—1，B—0 ---> T1—截止，T2导通，写入1

* 读取：

  * W—1，~W—1，Z正脉冲 ---> T1回路导通（即~W存在电流）读出0； T2回路导通（即W存在电流）读出1

<img src="..\..\assets\image-20241227082746382.png" alt="image-20241227082746382" style="zoom:40%;" />

* Z线：

  * 1——T5、T6导通，读写操作
  * 0——T5、T6断开，位线与内部线路脱离，信号保持状态

* 写入：

  * W—1，~W—0 ----> A—0，B—1 ---> C1充电，C2放电 ---> T1导通，T2截止，写入0

  * W—0，~W—1 ----> A—1，B—0 ---> C2充电，C1放电 ---> T2导通，T1截止，写入1

* 读取：
  * W—1，~W—1，Z正脉冲 ---> T1回路导通（即~W存在电流：~W--->T3--->A--->T1--->对地放电）读出0，W为C1充电至高电平，补充泄漏的电荷； T2回路导通（即W存在电流：：W--->T4--->B--->T2--->对地放电）读出1，~W为C2充电至高电平，补充泄漏的电荷

<img src="..\..\assets\image-20241227102555221.png" alt="image-20241227102555221" style="zoom:80%;" />

* 写入：
  * Z——1 ---> T导通 ---> W=1时，C充电，写入1；W=0时，C放电，写入0
* 读取：
  * W—1后断开，Z—1 ---> T导通，若C为1，则无电流，若C位0，则有电流

### 内存管理——页式管理

[页表相关内容](D:\course\操作系统\notes\05.md)

补充：多级页表

<img src="..\..\assets\1896043-20200506150416135-1747730577.jpg" alt="img" style="zoom:25%;" />

补充：**TLB**

[原文](https://zhuanlan.zhihu.com/p/108425561)

TLB的数据来源于页表，但TLB自身储存在cache中，保存虚拟地址---主存物理地址的映射

虚拟地址首先发往TLB确认是否命中，如果**TLB hit**直接可以得到物理地址，

​	将该地址分解为Tag、Index、Offset三部分，先通过Index定位到缓存行，再比较二者的Tag，

​		若缓存行中的 Tag 与物理地址中的 Tag 匹配，且缓存行的有效位（Valid Bit）为 1，则表示缓存命中（**Cache Hit**）

​		若不匹配，则表示缓存未命中（**Cache Miss**），从主存中加载（涉及各种映射——直接、组相联、全相联）

否则**TLB Miss**，在主存中一级一级查找页表获取物理地址。并将虚拟地址和物理地址的映射关系缓存到TLB中

<img src="..\..\assets\37507fb9d1a0fa3e6654b61c4448b35a.png" alt="在这里插入图片描述" style="zoom:60%;" />

* nG：是否是global映射（针对内核空间这种所有进程共享的映射关系）

  在最后一级页表中引入一个bit(non-global (nG) bit)代表是不是global映射，当虚拟地址映射物理地址关系缓存到TLB时，将nG bit也存储下来

  当判断是否命中TLB时，在比较tag相等后，再判断是不是global映射， 如果是的话，直接判断TLB hit，无需比较ASID。当不是global映射时，最后比较ASID判断是否TLB hit

* ASID（Address Space ID）：类似进程ID，用来区分不同进程的TLB表项

  当进程切换时，可以将页表基地址和ASID(可以从task_struct获得)共同存储在页表基地址寄存器中。当查找TLB时，硬件可以对比tag以及ASID是否相等(对比页表基地址寄存器存储的ASID和TLB表项存储的ASID)。如果都相等，代表TLB hit。否则TLB miss。当TLB miss时，需要多级遍历页表，查找物理地址。然后缓存到TLB中，同时缓存当前的ASID

**TLB shootdown**

[原文](https://www.educative.io/answers/what-is-tlb-shootdown)

The process of invalidating or updating the [translation lookaside buffer (TLB) ](https://www.educative.io/answers/what-is-tlb)in a computer system is referred to as a TLB shootdown

* 原因

  <img src="..\..\assets\image-20250105155734537.png" alt="image-20250105155734537" style="zoom:70%;" />

* 步骤

  <img src="..\..\assets\image-20250105155822900.png" alt="image-20250105155822900" style="zoom:70%;" />



#### else

不同进程就算是同样的虚拟地址，也会映射到不同的物理地址：

每个进程有自己单独的页目录，存储该进程自己的虚拟地址 → 物理地址映射关系

每次进程切换时，Linux 内核会：

- 修改 CPU 寄存器 `CR3`
- 把自己的页目录地址加载进去



### 内存保护

* 可执行空间保护：只把内存中的指令部分设置成“可执行”的，对于其他部分，比如数据部分，不给予“可执行”的权限
* 地址空间布局随机化：在内存空间随机去分配进程里不同部分（栈、堆、指令代码、库）所在的内存空间地址，让破坏者猜不出来



## Cache和Memory的映射方式

[原文](https://openatomworkshop.csdn.net/664ee89eb12a9d168eb716a9.html?dp_token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6MzE3Mjg0MywiZXhwIjoxNzM2Njk3ODMzLCJpYXQiOjE3MzYwOTMwMzMsInVzZXJuYW1lIjoibTBfNjMyNzM3OTUifQ.gQpB-mTXqxWd0OVp6BWB-AFQbHTOB4IVGugID5jAbgI&spm=1001.2101.3001.6650.6&utm_medium=distribute.pc_relevant.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7Eactivity-6-107317646-blog-53392315.235%5Ev43%5Epc_blog_bottom_relevance_base9&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7Eactivity-6-107317646-blog-53392315.235%5Ev43%5Epc_blog_bottom_relevance_base9&utm_relevant_index=13)

[原文2](https://www.cnblogs.com/east1203/p/11572500.html)

### 直接映射

主存中的一个块只能映射到Cache的某一特定块中去

<img src="..\..\assets\e2dd21583f6f850965512c750c183f7c.jpeg" alt="在这里插入图片描述" style="zoom:18%;" />

写入过程：

Cache中每一页的地址：页号+页内地址

主存中的每一页地址：页面标记+页号+页内地址

读入时，主存中的页载入Cache中对应页号的地址，并将页面标记放入在Cache对应页的标记中

读出过程：

1. 寻找Cache页号 ：CPU访问时，首先根据访存地址中的c位（页号），直接查出该主存对应的Cache的页号。

2. 检查：找到Cache的页号后，检查它的标记和主存的高t位是否一致。

   一致：一致则命中，再根据页内地址（b位），从Cache中读数据。

   不一致：不一致则未命中（失靶），CPU直接从主存中读出。

<img src="..\..\assets\a9ff5b81fcadebf3fc977a48a751f45b.jpeg" alt="在这里插入图片描述" style="zoom:25%;" />

### 全相联映射

主存中任一页可装入Cache内任一页

<img src="..\..\assets\0764113d5d16b3495bd7681ad2a835bf.jpeg" alt="在这里插入图片描述" style="zoom:25%;" />

读出过程：

相联存储器中有一张表：主存页号---Cache页号

1. 寻找Cache页号 ：给出主存地址后，让主存页号与目录表中各项的页号做相联比较。

   有相同的则讲对应的Cache页号取出，与页内地址拼接就形成了Cache地址。

   没有相同的则表示主存页没有装入Cache，失靶，去主存读。

<img src="..\..\assets\b524095f3e199d8a7e23de69e9210de1.jpeg" alt="在这里插入图片描述" style="zoom:15%;" />

### 组相联映射

<img src="..\..\assets\7e715bb8ce43487bbf28768fac32bd66.jpeg" alt="在这里插入图片描述" style="zoom:25%;" />