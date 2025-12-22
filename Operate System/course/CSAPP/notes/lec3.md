# 浮点数

* 只能精确表示`x/(2^k)`之和（`x`、`k`为任意整数）

  <img src=".\assets\image-20250919192138784.png" alt="image-20250919192138784" style="zoom:60%;" />

* 舍入方式：四舍六入五取偶（十进制） ➡ 看`w`位（需要保留的位数）后的数——若 < `1000…`则舍，若 > `1000…`则入；若 = `1000…`，则看第`w`位，向偶数（0）取整

## IEEE浮点数标准

$$
(-1)^s*M*2^E
$$

单精度（float in C）和双精度（double in C）的表示：

<img src=".\assets\image-20250919192446979.png" alt="image-20250919192446979" style="zoom:60%;" />

S：由`s`编码；符号位

E：由`exp`编码（但`E != exp`）

M：由`frac`编码（但`M != frac`）

### Normalized Values

`exp != 000…0` and `exp != 111…1`

* `E = exp - bias`
  * `bias = 2^(k-1) - 1`，`k`为`exp`的位数
    * 单精度：`exp = 1~254, bias = 127, E = -126~127`
    * 双精度：`exp = 1~2046, bias = 1023, E = -1022~1023`

* `M` 用`1.xxx`表示；`frac`只编码`M`小数点后的数，其个位默认为1，可以隐藏

### Denormalized Values

`exp = 000…0`

* `E = 1 - bias`
  * `bias`计算方法如上Normalized Values所示
* `M` 用`0.xxx`表示；`frac`只编码`M`小数点后的数，其个位默认为0，可以隐藏
* `frac = 000…0`时，有`+0`和`-0`

### Special Values

`exp = 111…1`

* 无穷——`frac = 000…0`
* NaN——`frac != 000…0`

### Overview

<img src=".\assets\image-20250919201953993.png" alt="image-20250919201953993" style="zoom:80%;" />

<img src=".\assets\image-20250919205409165.png" alt="image-20250919205409165" style="zoom:80%;" />

plus：在`exp`相同时，`frac`每递增1，整个浮点数递增一个相同的数——即浮点数以一个固定的间距递增，而这个间距随`exp`的增大而增大

<img src=".\assets\image-20250919202327963.png" alt="image-20250919202327963" style="zoom:80%;" />

## 浮点数计算

不符合结合律——两个大小相差过大的数相加，小的数会shift到被忽略；两个数相乘，`exp`可能会溢出

<img src=".\assets\image-20250919213601499.png" alt="image-20250919213601499" style="zoom:50%;" />

<img src=".\assets\image-20250919213645388.png" alt="image-20250919213645388" style="zoom:50%;" />

### 乘法

$$
(-1)^{s_1}*M_1*2^{E_1}\times(-1)^{s_2}*M_2*2^{E_2}\\
s=s_1 \text{ xor } s_2\\
M=M_1*M_2\\
E=E_1+E_2
$$

* 若`M>2`，`M`右移（并对溢出的位做舍入操作），增加`E`

### 加法

对齐 ➡ 相加 ➡ 对齐

小阶看齐大阶，尾数右移

## 浮点数类型转换

* double / float ➡ int
* int ➡ double：如果 `int`的位数 ≤ 53 位（double 的 frac），转换时不会丢失精度
* int ➡ float：如果 `int`的位数 ≤ 23 位（float 的 frac），转换时不会丢失精度；否则高位舍入