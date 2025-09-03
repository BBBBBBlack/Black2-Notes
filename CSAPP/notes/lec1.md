## 有符号与无符号整数

（以32bit——4字节的int为例）

### unsigned int

只有正
$$
取值范围：0:2^{32}-1
$$

### signed int

有正负

* 用补码表示：
  $$
  取值范围：-2^{31}:2^{31}-1\\
  $$

* 

<img src=".\assets\image-20250718193935597.png" alt="image-20250718193935597" style="zoom:35%;" />
$$
U_{max}=T_{max}*2+1\\
T_{max}+1=|T_{min}|(在数值上，不考虑计算机上计算时各种溢出的情况)\\
$$
计算机上运行得：
$$
-T_{min}=T_{min}\\
\\
以一个4bit的有符号数为例——x的补码取反+1\rightarrow-x：\\
1000取反+1\rightarrow1000\\
最小的有符号数的相反数是其本身
$$

### 转换

* `signed int`和`unsigned int`计算 > `signed int`变`signed int`

### 类型转换

#### 扩展

* `unsigned int`：高位填0
* `signed int`：高位填其原本最高位的那个数字

#### 截断

删去高位

