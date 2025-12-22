# BPF CO-RE (Compile Once – Run Everywhere)

[BPF CO-RE]([BPF CO-RE (Compile Once – Run Everywhere)](https://nakryiko.com/posts/bpf-portability-and-co-re/))

**eBPF的可移植性问题：**不同的内核版本，其内部的数据结构往往不一致（struct中字段的重命名、增减等），对于那些需要查看内核内部数据的BPF Program，往往不具有可移植性（按照本地内核的数据结构进行编译（编译完对字段的访问都转化为偏移量了），往往在其他版本的内核上无法运行——不同版本的内核不一定有某个字段，不一定处在这个偏移位置上，可能读到垃圾值）

### BTF (BPF Type Format)

* 在现代 Linux 内核（开启 `CONFIG_DEBUG_INFO_BTF=y`）中，被嵌入到了内核二进制文件（vmlinux）里
* 二进制数据，当前运行内核的所有**数据结构定义**
* 通过`bpftool btf dump file /sys/kernel/btf/vmlinux format c`查看（一般输出为`vmlinux.h`被.bpf.c文件include）

### Compiler

* 将 C 语言翻译成 BPF 机器指令

* 生成`.BTF` 段

* 生成`.BTF.ext`段——识别代码中需要CO-RE支持的操作，在`.BTF.ext`段生成CO-RE Relocations记录

  ```c++
  // 位于 .BTF.ext 段
  struct bpf_core_relo {
      __u32 insn_off;       // 1. 去修改哪条指令？
      __u32 type_id;        // 2. 依据哪个类型？ (关键点！这里指向 .BTF 段)
      __u32 access_str_off; // 3. 访问路径是什么？("0:1")
      ...
  };
  ```

### libbpf

接收编译后的 BPF ELF 目标文件，根据需要进行后处理，设置各种内核对象（映射、程序等），并触发 BPF 程序加载和验证

* 读取`.BTF.ext`段的 CO-RE Relocations 记录
* 通过`bpf_core_relo.type_id`找`.BTF`段中对应的结构定义，并通过`bpf_core_relo.access_str_off` 确定 BPF Program 想访问的成员字段
* 去运行环境的内核BTF中找到同名结构体，在结构体里，根据字段名称去搜索它在当前内核中的 实际字节偏移量
* 修改在编译环境中编译生成的 BPF 机器指令，修改其偏移量（原本的偏移量是在编译时生成的，是编译环境下，而非当前运行环境下，该字段的偏移量）