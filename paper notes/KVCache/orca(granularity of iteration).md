# orca(granularity of iteration)

在批处理多个请求时，请求生成的结果文本长度不一致，但在批处理时，所有请求需要同时结束迭代，增大了生成文本短的请求的返回时延，同时增大了下一批请求的返回时延

* 使用批处理的attention不能在迭代的过程中动态地往当前批中增减请求
  $$
  存储的KV-Cache矩阵：\\
  (batch\_size,head\_number,已经生成的tokens数,d\_model/head\_number)\\
  self-attention：QK^T:(batch\_size,head\_number,1,d\_model/head\_number)\\
  K^T:batch\_size,head\_number,d\_model/head\_number,已经生成的tokens数)\\
  当K的shape中已经生成的tokens数不一致时，无法使用矩阵乘法
  $$
  

LLM的整体工作流程

![\<img alt="image-20241112020704569" style="zoom:80%;" data-attachment-key="VZZ8MV7P" src="attachments/VZZ8MV7P.png" ztype="zimage">](attachments/VZZ8MV7P.png)

*   inference serving system（Triton Inference Server、TensorFlow Serving）
*   execution engines（TensorRT、TVM、TensorFlow）

1.  scheduler从request queue中检索一批请求
2.  将这批请求提交给execution engine
3.  execution engine处理请求，返回结果
4.  将结果返回serving system



## 挑战

### C1：提前完成和延迟加入的请求

在批处理多个请求时，请求生成的结果文本长度不一致，但在批处理时，所有请求需要同时结束迭代，增大了生成文本短的请求的返回时延，同时增大了下一批请求的返回时延

**S1**：Iteration-level scheduling（迭代级调度）

* 选择下一个要运行的请求
* 调用引擎对选定的请求执行**一次迭代**
* 接收预定迭代的执行结果

<img src="..\assets\image-20241115230136288.png" alt="image-20241115230136288" style="zoom:70%;" />

* Endpoint将收到的请求放入request pool
* Scheduler从请求池中拿出4个请求的tokens送入execution engine
* execution engine生成一个请求的一个token（迭代一次）
* 若该token不是结束符（这个请求还没结束）
* 更新request pool



### C2：批处理任意一组请求

* 两个请求都处于启动阶段，并且每个请求都有不同数量的输入token（例如，图 4 中的 x3: [2, H] 和 x4: [3, H]）
* 两者都处于增量阶段，并且各自处理彼此不同索引处的令牌（x1 和 x2，KV-Cache的张量不一样）
* 每个请求处于不同的阶段：启动或增量（x1: [1, H] 和 x3: [2, H]）

仅当两个选定的请求处于同一阶段、具有相同数量的输入token（在启动阶段的情况下）或具有相同的token索引（在增量阶段的情况下）时，批处理才适用

**S2**：selective batching（选择性批处理）

非注意力层（Linear、LayerNorm、Add 和 GeLU 操作等）可以将向量堆叠起来计算

<img src="..\assets\image-20241115234417826.png" alt="image-20241115234417826" style="zoom:60%;" />

Attention K/V manager——维护每个请求的KV值
