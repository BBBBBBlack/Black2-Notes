![image-20241117175446206](..\assets\image-20241117175446206.png)

* 输入sequence x，将其分为N个块，分配到N个主机上
* 在每个主机上，计算其分配到的sequence片段的QKV
* 对于每一台主机，以下程序循环并行：
  * 使用本地的QKV计算attention层的输出，将新的KV送入下一个主机，接收前一个主机的QKV
  * 将本地attention层的输出输入前馈神经网络



疑问：每个主机的前馈神经网络的输出要怎么处理，才能得到一个完整的句子？

​			除了第一次迭代，每台主机在接下来的迭代中，输入的是自己的前一次输出，还是上一台主机的前一次输出？



## 源代码部分解析（目前看得懂的部分）

[ring attention的pytorch实现](https://github.com/lucidrains/ring-attention-pytorch)

`mp.spawn()`函数来启动多个进程，并将指定的`start`函数并行地在这些进程上运行（开启多个进程运行ring attention代表文章中的多个主机）

```python
mp.spawn(
    start,
    args = (
        world_size,
        batch_size,
        batch_size_var_len,
        seq_len,
        num_buckets,
        num_sharded_batches,
        causal,
        striped_ring_attn,
        model_dim,
        heads,
        num_grouped_query_heads,
        dim_head,
        use_cuda,
        compare_regular_attn
    ),
    nprocs = world_size,
    join = True
)
```



每台主机将新的KV送入下一个主机，接收前一个主机的QKV

```python
# ring_attention_pytorch/ring.py

def send_and_receive_(x, receive_buffer, send_to_rank, receive_from_rank):
    '''
    torch.distributed.P2POp()：PyTorch中用于创建点对点通信操作的类。P2POp表示Point-to-Point 		Operation（点对点操作），用于实现进程之间的直接通信。通过创建P2POp对象，可以指定发送数据、接收数据的	 进程以及通信方式（如isend和irecv）等参数，以实现进程之间的数据交换和通信
    '''
    send_op = dist.P2POp(dist.isend, x, send_to_rank)
    recv_op = dist.P2POp(dist.irecv, receive_buffer, receive_from_rank)

    reqs = dist.batch_isend_irecv([send_op, recv_op])

    for req in reqs:
        req.wait()

    dist.barrier()
```

调用：

接收左边的，发送给右边的

```python
send_and_receive_(x, receive_buffer, circular_rank_right(ring_size = ring_size), circular_rank_left(ring_size = ring_size))
```

