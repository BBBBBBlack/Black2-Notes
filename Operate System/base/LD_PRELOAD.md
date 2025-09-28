# LD_PRELOAD

Linux的一个环境变量，强制操作系统在加载其他所有库之前，**最优先加载**指定的那个 [`.so`](编译与链接.md) 动态库

命令：

```sh
# 编译.so动态库
gcc -fPIC -shared -o hook.so hook.c -ldl

# 编译原程序
gcc -o main main.c

# 运行
LD_PRELOAD=./hook.so ./main
```

## 1. 替换相同函数

由于LD_PRELOAD让自定义的.so库优先加载，动态链接器在查找 `strcmp` 时，自定义的.so库在最前面，故最先找到自定义版本

```c
#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
  if(strcmp(argv[1], "test")) {
    printf("Incorrect password\n");
  } else {
    printf("Correct password\n");
  }
  return 0;
}
```

```c
#include <stdio.h>
#include <string.h>
#include <dlfcn.h>

/* hook的目标是strcmp，所以typedef了一个STRCMP函数指针，
 * hook的目的是要控制函数行为，从原库libc.so.6中拿到strcmp指针，保存成old_strcmp以备调用. */
typedef int(*STRCMP)(const char*, const char*);

int strcmp(const char *s1, const char *s2) {
  static void *handle = NULL;
  static STRCMP old_strcmp = NULL;

  if(!handle) {
    // 在刚刚打开的 C 库句柄中，查找原始的 strcmp 函数的地址
    handle = dlopen("libc.so.6", RTLD_LAZY);
    old_strcmp = (STRCMP)dlsym(handle, "strcmp");
  }
  printf("oops!!! hack function invoked. s1=<%s> s2=<%s>\n", s1, s2);
  // 返回和替换的原函数一致的返回值（必须遵循原函数规范！）
  // 主动调用了之前保存的原始程序 strcmp 函数指针 (old_strcmp)，并将参数原封不动地传过去
  // 然后将原程序的 strcmp 函数的返回值作为自己的返回值，返回给原程序调用者（即 main 函数）
  return old_strcmp(s1, s2);
}
```

## 2. 其他（注册通用钩子）

将自定义通用函数 `hook` 注册给 `libsyscall_intercept` 库提供的钩子点 `intercept_hook_point`（这是.so库的自定义功能，和LD_PRELOAD无关，LD_PRELOAD只负责优先加载）

当程序发起任何系统调用时，`libsyscall_intercept` 都会先暂停它，再调用注册好的 `hook` 函数

* 若`hook return 0`，则原函数不会被执行
* 否则继续执行原函数

```c
void* (*libc_mmap)(void *addr, size_t length, int prot, int flags, int fd, off_t offset) = NULL;
int (*libc_munmap)(void *addr, size_t length) = NULL;
void* (*libc_malloc)(size_t size) = NULL;
void (*libc_free)(void* ptr) = NULL;

static int hook(long syscall_number, long arg0, long arg1, long arg2, long arg3,	long arg4, long arg5,	long *result)
{
	if (syscall_number == SYS_mmap) {
	  return mmap_filter((void*)arg0, (size_t)arg1, (int)arg2, (int)arg3, (int)arg4, (off_t)arg5, (uint64_t*)result);
	} else if (syscall_number == SYS_munmap){
    return munmap_filter((void*)arg0, (size_t)arg1, (uint64_t*)result);
  } else {
    // TODO: add madvise and read/write interception here too
    // ignore non-mmap system calls
		return 1;
	}
}

// 一个进程执行一遍
static __attribute__((constructor)) void init(void)
{
  libc_mmap = bind_symbol("mmap");
  libc_munmap = bind_symbol("munmap");
  libc_malloc = bind_symbol("malloc");
  libc_free = bind_symbol("free");
  intercept_hook_point = hook;

  extmem_init();
}
```

