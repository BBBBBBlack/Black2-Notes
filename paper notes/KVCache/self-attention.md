# self-attention

<img src="..\assets\image-20241012111206267.png" alt="image-20241012111206267" style="zoom:28%;" />

输入：n个向量（n个向量可能是一个长度不定的句子，每个向量表示一个word——n不确定）

输出：n个向量（每个向量包含了其他 n - 1 个向量的信息——即上下文的信息）

将n个向量分别输入n个全连接网络

[attention is all you need](..\paper)



### 计算相关性

计算每个向量和其他向量的相关性

* **Dot-product**

  <img src="..\assets\image-20241012112516694.png" alt="image-20241012112516694" style="zoom:50%;" />

  具体操作：计算a1和其他向量的相关度

  <img src="..\assets\image-20241012113137512.png" alt="image-20241012113137512" style="zoom:50%;" />

  <img src="..\assets\image-20241012130424412.png" alt="image-20241012130424412" style="zoom:50%;" />
  $$
  \alpha_{i,j}=softmax((q^i)^T k^j/\sqrt {d-model})
  $$
  
* Additive

<img src="..\assets\image-20241012112631845.png" alt="image-20241012112631845" style="zoom:50%;" />

### 抽取重要信息

根据相关性抽取出每个向量的重要信息Wimage-20241014012844552

<img src="..\assets\image-20241012113532636.png" alt="image-20241012113532636" style="zoom:50%;" />
$$
b^1=\sum_i \alpha_{1,i}'v^i
$$
<img src="..\assets\image-20241012130636900.png" alt="image-20241012130636900" style="zoom:50%;" />

### 插入位置资讯

[positional encoding](..\paper)
$$
e^i+a^i\\
e^i为位置信息，在a^i上插入位置信息
$$

## Transformer

sequence to sequence

输入输出向量个数都不定

<img src="..\assets\image-20241013115003924.png" alt="image-20241013115003924" style="zoom:50%;" />

### encoder

<img src="..\assets\image-20241013114930346.png" alt="image-20241013114930346" style="zoom:50%;" />

#### 一个block的结构

* 输入inputs向量 `X` 并加入位置信息（positional encoding）

* 将 `X` 输入self-attention层，得到 `X'` ，将 `X + X'` 得到 `X''`

* 对 `X''` 做normalize（layer nomalize）

  <img src="..\assets\image-20241013115757606.png" alt="image-20241013115757606" style="zoom:50%;" />

* 将 `X''` 输入全连接神经网络FC，得到 `X'''` ，将 `X'' + X'''` 得到 `X''''`**（residual）**

* 对 `X''''` 做normalize（layer nomalize）

### decoder

Autoregressive

#### 输入输出

<img src="..\assets\image-20241013121632158.png" alt="image-20241013121632158" style="zoom:50%;" />

**自回归**：输入(1,t)个词 ----- 输出(2,t+1)个词-----输入(1,t+1)个词-----输出(2,t+2)个词

* 头次输入：encoder输出的向量 + BEGIN（初始的输入向量）
* 将decoder输出的向量 + encoder的输出向量作为输入，循环
* decoder输出一个字典向量（单词/汉语中的汉字：0~1之间的可能性）
* 当decoder输出END（可以用BEGIN表示）时，结束语句

#### 具体结构

<img src="..\assets\image-20241013122059148.png" alt="image-20241013122059148" style="zoom:50%;" />

* masked self-attention：只考虑当前输入向量即其左边的向量，计算b

* corss attention

  <img src="..\assets\image-20241014012610151.png" alt="image-20241014012610151" style="zoom:50%;" />

  * 将encoder输出的n个向量和decoder中masked self-attention输出的一个向量连接
  * <img src="..\assets\image-20241014012844552.png" alt="image-20241014012844552" style="zoom:40%;" />

### train

在训练时，decoder输入正确答案（teacher forcing）

### Tips

guided attention：解决输入输出不对齐的问题（如语音合成，语音识别输出的文字，声音缺少）

beam search：局部最优→全局最优

scheduled sampling：训练时向decoder输入以下错误



## GPT

结构：transformer的decoder部分，并拆掉一个masked multi-head attention

<img src="..\assets\image-20241112005022098.png" alt="image-20241112005022098" style="zoom:60%;" />

