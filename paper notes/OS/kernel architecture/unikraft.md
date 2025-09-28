# Unikraft

<img src="..\..\assets\unikraft-architecture.svg" alt="Overview of Unikraft's architecture. All components are micro-libraries that have their own Makefile and Kconfig configuration files, and so can be added to the unikernel build independently of each other.  APIs are also micro-libraries that can be easily enabled or disabled via a Kconfig menu; unikernels can thus compose which APIs to choose to best cater to an application's need." style="zoom:90%;" />

## 组成

### Micro-Libraries

* 有自己的Makefile和Kconfig

  * Kconfig：定义了这个库可以配置的选项

    选择需要的功能选项，写入.config文件

  * Makefile：定义了一系列的规则，说明一个项目中的各个文件的依赖关系、源代码（`.c`, `.cpp`, `.S` 文件）如何生成目标文件（`.o` 文件），如何链接成可执行文件

    根据 `.config` 中变量，使用条件判断语句来决定具体要执行哪些操作

    ```shell
    # --- 变量定义 ---
    # 使用变量可以让 Makefile 更易于维护和修改
    
    # 定义C++编译器
    CXX = g++
    
    # 定义编译参数
    # -std=c++11: 使用 C++11 标准
    # -Wall -Wextra: 开启所有常用和额外的警告，帮助写出更规范的代码
    CXXFLAGS = -std=c++11 -Wall -Wextra
    
    # 定义最终生成的可执行文件名
    TARGET = helloworld
    
    # 自动获取所有 .cpp 源文件
    SOURCES = $(wildcard *.cpp)
    
    # 根据源文件自动推导出所有中间目标文件名 (将 .cpp 替换为 .o)
    OBJECTS = $(SOURCES:.cpp=.o)
    
    
    # --- 规则定义 ---
    
    # 默认规则：当直接运行 `make` 时，会执行这个名为 "all" 的规则
    # 它依赖于最终的可执行文件 $(TARGET)
    all: $(TARGET)
    
    # 链接规则：如何从所有 .o 文件生成最终的可执行文件
    # $(TARGET) 依赖于所有的 $(OBJECTS)
    $(TARGET): $(OBJECTS)
    	# <--- 注意：这一行必须以一个 Tab 键开头，而不是空格！
    	$(CXX) $(CXXFLAGS) -o $@ $(OBJECTS)
    
    # 编译规则：如何从一个 .cpp 文件生成一个 .o 文件
    # 这是一个“模式规则”，可以匹配所有的 .cpp -> .o 的转换
    # $@ 代表规则的目标 (比如 main.o)
    # $< 代表规则的第一个依赖 (比如 main.cpp)
    %.o: %.cpp
    	# <--- 注意：这一行必须以一个 Tab 键开头！
    	$(CXX) $(CXXFLAGS) -c $< -o $@
    
    # 清理规则：用于删除所有编译生成的文件
    clean:
    	# <--- 注意：这一行必须以一个 Tab 键开头！
    	rm -f $(TARGET) $(OBJECTS)
    
    # 伪目标声明：告诉 make，"all" 和 "clean" 不是真实的文件名
    .PHONY: all clean
    ```

* 所有实现相同 API 的微库都是可互换

* 可以来自外部库项目（OpenSSL、musl、Protobuf）、应用程序（SQLite、Redis）甚至平台（Solo5、Firecracker、Raspberry Pi 3）的功能的库

#### 分层

* **LIBC Layer**：提供了标准C库（LIBC）的API接口——`printf`, `malloc`, `fopen`
  * `musl` : 轻量级、兼容性好且高效的C标准库实现 
  * `newlib` : 常用于嵌入式系统和unikernel的C标准库
  * `nolibc`：unikraft自带
* **POSIX COMPAT Layer**：为兼容现有应用程序而设计
  * syscall-shim：拦截上层LIBC发出的标准系统调用（syscalls），转换为Unikraft内部的API调用
* **OS PRIMITIVES Layer**：操作系统最核心、最基础的功能——`ukalloc`内存分配器、`uksched`调度器、`ukboot` 引导程序、`uknetdev` / `ukblockdev`
* **PLATFORM Layer**：为上层提供了统一的接口，使得同一个 Unikernel 镜像可以无需修改就运行在 KVM、Xen 等不同的虚拟化环境上

### Build System

选择在应用程序构建中使用哪些微库

<img src="..\..\assets\build_uk.svg" alt="Steps of the Unikraft build process" style="zoom:100%;" />

* 使用`make menuconfig`工具，根据应用程序的需求，从`Config.uk`中选择需要的配置，生成`.config`
* `Makefile`整合各个Mcro-Libraries的`Makefile.uk`与`source code`
* `make`根据`Makefile`定义的规则，生成`image`（可执行文件）
* `image`由`kvm/ELF Loader`启动、运行

**Config.uk**

```shell
config APPELFLOADERNET
bool "Configure ELF loader application (for binary compatibility) with networking support"
default y

	# Select app-elfloader component.
	select APPELFLOADER_DEPENDENCIES

	# Configurations options for app-elfloader
	# (they can't be part of the template atm)
	select APPELFLOADER_BRK
	select APPELFLOADER_CUSTOMAPPNAME
	select APPELFLOADER_STACK_NBPAGES
	select APPELFLOADER_VFSEXEC_EXECBIT
	……
```

**Makefile.uk**

```shell
$(eval $(call addlib,appcfs))

APPCFS_SRCS-y += $(APPCFS_BASE)/cat.c
```

**Makefile**

```shell
UK_ROOT ?= $(PWD)/workdir/unikraft
UK_BUILD ?= $(PWD)/workdir/build
UK_APP ?= $(PWD)
LIBS_BASE = $(PWD)/workdir/libs
UK_LIBS ?=

.PHONY: all

all:
	@$(MAKE) -C $(UK_ROOT) L=$(UK_LIBS) A=$(UK_APP) O=$(UK_BUILD)

$(MAKECMDGOALS):
	@$(MAKE) -C $(UK_ROOT) L=$(UK_LIBS) A=$(UK_APP) O=$(UK_BUILD) $(MAKECMDGOALS)
```

### 优化方法：

* 通过消除系统调用开销、减少镜像大小和内存消耗，以及选择高效的内存分配器来优化**未修改**的应用程序。

* 通过调整应用程序以利用较低级别的 API，在任何性能至关重要的场合（例如，寻求高磁盘 I/O 吞吐量的数据库应用程序）进行**专门化**