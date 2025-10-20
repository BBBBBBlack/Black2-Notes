# LLVM IR

## 数据区和符号表

### 链接类型

|     LLVM IR链接类型      | ELF Binding | ELF Visibility |      符号表      |             说明             |
| :----------------------: | :---------: | :------------: | :--------------: | :--------------------------: |
|       **private**        |     N/A     |      N/A       |     ❌不出现      |    完全内部，可能被优化掉    |
|       **internal**       |  STB_LOCAL  |  STV_DEFAULT   | ✅出现(仅.symtab) |          本模块可见          |
|       **external**       | STB_GLOBAL  |  STV_DEFAULT   |      ✅出现       |  全局可见，可被其他模块引用  |
| **available_externally** |     N/A     |      N/A       |     ❌不出现      | 定义在其他模块，本模块有副本 |
|       **linkonce**       |  STB_WEAK   |  STV_DEFAULT   |      ✅出现       |   弱定义，可被相同符号覆盖   |
|         **weak**         |  STB_WEAK   |  STV_DEFAULT   |      ✅出现       |            弱定义            |
|        **common**        | STB_GLOBAL  |  STV_DEFAULT   |   ✅出现(.bss)    |       未初始化全局变量       |

#### ELF符号

绑定类型：

* STB_LOCAL   (LOCAL)   // 局部符号；STB_GLOBAL  (GLOBAL)  // 全局符号；STB_WEAK    (WEAK)    // 弱符号

可见性：

* STV_DEFAULT   (DEFAULT)   // 默认可见；STV_INTERNAL  (INTERNAL)  // 内部可见；STV_HIDDEN    (HIDDEN)    // 隐藏；STV_PROTECTED (PROTECTED) // 保护

### 可见性

决定一个全局符号（函数或变量）在**动态共享库（DSO, 即 .so 文件）**被创建和加载时，如何被“看见”和“使用”

抢占：在运行时，动态链接器是否可以被指示（例如通过 `LD_PRELOAD`）用另一个模块中的同名符号来替换这个符号的定义

dso_local——不可抢占；~dso_local——可抢占

|   **属性**    | **导出到 .dynsym? (外部可见)** | **可被抢占 (dso_local)?** |  **内部引用性能**   |      **用途**       |
| :-----------: | :----------------------------: | :-----------------------: | :-----------------: | :-----------------: |
|  **default**  |            ✅ **是**            |         ✅ **是**          | **慢** (需 GOT/PLT) | 公共 API (可被覆盖) |
|  **hidden**   |            ❌ **否**            |         ❌ **否**          |  **快** (直接访问)  |    内部实现细节     |
| **protected** |            ✅ **是**            |         ❌ **否**          |  **快** (直接访问)  | 公共 API (不可覆盖) |

### 可抢占性

符号（symbol）的定义和所有对它的引用都位于同一个链接单元（linkage unit）内

### Example: 

from C program to LLVM IR：

```c
int var1 = 1;

// 当前文件定义，其他文件不可使用
static int var2 = 2;

__attribute__((visibility("hidden")))
int var3 = 3;
```

```c
@var1 = dso_local global i32 1, align 4		// 链接类型：external (默认)；可见性：default (默认)
@var2 = internal global i32 2, align 4		// 可见性：hidden；抢占：dso_local
@var3 = hidden global i32 3, align 4		// 链接类型：external (默认)；
```

## 寄存器和栈

```c
// 寄存器中的变量
%local_variable = add i32 1, 2
// 栈上的变量
%local_variable = alloca i32
```

### 虚拟寄存器

前端/优化器 (IR)：

LLVM 假设它有**无限虚拟寄存器**可用——优化器在分析和转换代码时，无需担心目标 CPU（比如 x86-64）只有 16 个通用寄存器这种物理限制

后端：

寄存器分配（Register Allocation）

- 当所需寄存器数量较少时，直接使用caller-saved register，即不需要保留的寄存器
- 当caller-saved register不够时，将callee-saved register（某些值不允许改变的寄存器）原本的值压栈，然后使用callee-saved register
- 当寄存器用光以后，就把多的虚拟寄存器的值压栈

分配器算法： `Basic`, `Fast`, `Greedy`, `PBQP`等，目标为最小化到栈的溢出（Spilling/Reloading）次数