## Code

### 加载流程

eBPF程序定义的结构——用于数据存储和**共享**（eBPF-eBPF or eBPF-用户态程序）的 `map` 类型

```c++
// 定义一个哈希表（表名，键类型，值类型，操控表的变量名，最大容量）
BPF_TABLE("lru_hash", struct XFSMTableKey,  struct XFSMTableLeaf,  xfsm_table,  10000);
// 声明数组类型的数据结构
BPF_ARRAY(num_processed, u64, 1);		// 处理的包的数量
BPF_ARRAY(all_features, s64, 12);		// 特征数据
BPF_ARRAY(children_left, s64, 123);		// 决策树中，每个节点的左子节点的相关数据
BPF_ARRAY(children_right, s64, 123);	// 决策树中，每个节点的右子节点的相关数据
BPF_ARRAY(value, s64, 123);				// 决策树节点的值
BPF_ARRAY(feature, s64, 123);
BPF_ARRAY(threshold, s64, 123);			// 决策树节点的阈值
```



编译 > 加载 > 验证

```c++
ebpf::BPF bpf;
auto res = bpf.init(ebpf_program);
```



用户态程序获取和内核态eBPF程序共享的map（BPF_TABLE、BPF_ARRAY等），将决策树的数据写入这些map中

```c++
ebpf::BPFArrayTable<int64_t> children_left_table = bpf.get_array_table<int64_t>("children_left");
for (size_t i = 0; i < children_left.size(); i++)
{
    res = children_left_table.update_value(i, children_left[i]);
    assert(res.code() == 0);
}
```



将`filter`函数指定为`BPF_PROG_TYPE_SOCKET_FILTER`类型——用于网络数据包过滤，内核会根据这个类型的标识，知道这个程序是用于网络数据包的处理

返回`filter`的文件描述符`fd`，之后将 eBPF 程序附加到套接字时需要用到的标识符

```c++
int fd;
res = bpf.load_func("filter", BPF_PROG_TYPE_SOCKET_FILTER, fd);
```



将一个原始socket（直接与网卡进行交互。应用程序可以通过raw socket访问网络层及以下的数据包）绑定到`eth0`以太网卡上

数据包首先到达网卡，然后根据网卡上的协议类型和目标 IP 地址传递到正确的socket

将`fd`指定的eBPF程序attach到socket `sd`上

```c++
int sd = bpf_open_raw_sock("eth0");
// SO_ATTACH_BPF——将一个 eBPF 程序附加到套接字上
ret = setsockopt(sd, SOL_SOCKET, SO_ATTACH_BPF, &fd, sizeof(fd));
```

### 运行时

* 解析数据包
* 获取输入的特征

#### ML具体实现

```c++
for (uint64_t i = 0; i < MAX_TREE_DEPTH; i++) {
    // bpf_trace_printk("i: %lu\n", i);
    int64_t* current_left_child = children_left.lookup(&current_node);
    int64_t* current_right_child = children_right.lookup(&current_node);

    int64_t* current_feature = feature.lookup(&current_node);
    int64_t* current_threshold = threshold.lookup(&current_node);

    if (current_feature == NULL || current_threshold == NULL || current_left_child == NULL || current_right_child == NULL || *current_left_child == TREE_LEAF) {
        break;
    } else {
        int64_t* real_feature_value = all_features.lookup((int*) current_feature);
        if (real_feature_value != NULL) {
            if (*real_feature_value <= *current_threshold) {
                current_node = (int) *current_left_child;
            } else {
                current_node = (int) *current_right_child;
            }
        } else {
            break;
        }
    }
}

int64_t* correct_value = value.lookup(&current_node);
```

