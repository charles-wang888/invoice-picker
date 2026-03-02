# 发票凑数神器

从 **X 张发票** 中选出 **Y 张**，使总金额 **≥ Z** 且**尽可能接近 Z**。本项目提供算法内核与 Web 应用，支持凑单求解、多解去重、分页展示与 CSV 导出。

---

## 背景

市面上有一款名为 **「Excel880」** 的软件，专门用来解决凑发票问题，但其实现较为依赖大语言模型（LLM）。凑发票本质是经典的 **NP 完全**问题：在计算量较大时（例如上万张发票中选出上千张凑目标金额），很多 AI 在**算法设计与实现**上表现并不理想。因此，本项目**自行实现了针对该问题的确定性算法**（排序 + 贪心 + 交换），不依赖 LLM，在给定规模下可稳定、可控地给出可行解并尽量逼近目标金额。

---

## 问题定义

**输入：**

- X 张发票，每张面额为 > 0 的浮点数（精确到小数点后 2 位）
- 目标选出 Y 张
- 目标金额 Z（元）

**输出：**

- 一组或多组解，每组为恰好 Y 张发票的列表
- 每组满足：总金额 ≥ Z，且总金额尽可能接近 Z
- 误差率：(总金额 − Z) / Z × 100%

**复杂度：** 该问题是** NP 完全**的（带基数约束的子集和问题），在 X、Y 较大时（如 10000 张选 1000 张）无法在多项式时间内求得精确最优解。本算法采用**启发式**，在保证可行性的前提下尽量逼近最优。

---

## 算法详解

### 一、总体策略：排序 + 贪心初始解 + 交换改进

算法分为三个阶段：

1. **排序阶段**：对所有发票按面额排序，为后续贪心奠定基础
2. **贪心初始解**：快速得到一个满足「≥ Z 且恰好 Y 张」的可行解
3. **交换改进**：在保持可行性前提下，反复用「小额未选」换「大额已选」，逐步逼近 Z

该策略的**时间复杂度**为 O(X log X) + O(R·X·Y)，其中 R 为交换轮数，与目标金额 Z 无关，适用于大规模数据。

---

### 二、阶段一：排序

**目的：** 让金额有序，便于贪心选取和交换时快速定位「大额」「小额」。

**实现：**

- 默认按金额**从大到小**排序（`sort_descending=True`）
- 同金额时，可用 `sort_tie_break_seed` 打乱顺序，得到不同的初始解，进而产生多种组合

**伪代码：**

```
sorted_invoices = sort(invoices, by=amount, descending=True)
# 可选：同金额时用随机 seed 决定先后，以产生不同组合
```

---

### 三、阶段二：贪心初始解

**目的：** 在已排序列表中，尽快得到一个「恰好 Y 张且总金额 ≥ Z」的可行解。

**思路：**

1. 先取**前 Y 张**（即金额最大的 Y 张）
2. 若这 Y 张的总金额已经 ≥ Z，则得到初始解
3. 若不足 Z，则从未选中**依次加入最大面额**，直到总金额 ≥ Z
4. 若此时已选张数 > Y，则**去掉金额最小的若干张**，在保持总金额 ≥ Z 的前提下，将张数截断为 Y

**伪代码：**

```
chosen = sorted_invoices[0 : Y]
unchosen = sorted_invoices[Y : ]
total = sum(chosen)

if total >= Z:
    return chosen, unchosen, total

# 不足时：从未选中加入大额，直到 >= Z
for inv in unchosen (从大到小):
    chosen.append(inv)
    unchosen.remove(inv)
    total += inv.amount
    if total >= Z: break

# 若 chosen 多于 Y 张，去掉最小的若干张（保持 total >= Z）
while len(chosen) > Y and (total - chosen最小) >= Z:
    total -= chosen最小
    unchosen.append(chosen.pop())
```

该初始解**保证可行**（若原始数据能凑到 Z），但总金额通常远大于 Z，需要后续交换来降低。

---

### 四、阶段三：交换改进

**目的：** 在保持「总金额 ≥ Z、张数 = Y」的前提下，用「未选中的小额」换「已选中的大额」，使总金额逐步接近 Z。

**单轮交换逻辑：**

1. 从已选集合中选一张**大额**发票 out
2. 从未选集合中选一张**小额**发票 in（满足 in.amount < out.amount）
3. 若交换后：新总金额 = total - out + in **仍 ≥ Z**，且**严格小于**原总金额，则执行交换
4. 每轮至多执行**一次**交换，然后进入下一轮

**关键约束：**

- 可行性：`new_total >= Z - tolerance`
- 单调递减：`new_total < total - min_improvement`（`min_improvement` 默认 0.01，防止无效微小交换）
- 交换方向：必须用更小的换更大的，即 `in.amount < out.amount`

**迭代顺序（优化收敛速度）：**

- 已选集合按**金额降序**遍历，优先换出大额
- 未选集合按**金额升序**遍历，优先换入小额
- 这样有利于每轮得到**最大降幅**，加快收敛

**终止条件：**

- 本轮无法找到任一满足条件的交换；或
- 达到预设的 `max_swap_rounds`（与「初始和 − Z」的差距动态计算，差距大时轮数更多）

**伪代码：**

```
while True:
    for out in chosen (按金额降序):
        if total - out.amount < Z: continue  # 换出会导致不足
        for in in unchosen (按金额升序):
            if in.amount >= out.amount: continue
            new_total = total - out.amount + in.amount
            if new_total < Z: continue
            if new_total >= total - min_improvement: continue
            # 执行交换
            chosen.remove(out); chosen.append(in)
            unchosen.remove(in); unchosen.append(out)
            total = new_total
            break  # 本轮只做一次交换
    if 本轮未发生交换: break
```

---

### 五、多解策略：不同 seed 得到多种组合

为得到 **Top 3** 等不同解：

- 使用 3 个不同的 `sort_tie_break_seed`（如 None、42、123）
- 同金额发票的排序顺序不同 → 贪心初始解不同 → 交换收敛到不同的局部最优
- 对结果按「选中发票 ID 集合」去重，只保留不同的组合

---

### 六、时间复杂度

| 阶段       | 复杂度                         |
|------------|--------------------------------|
| 排序       | O(X log X)                     |
| 贪心初始解 | O(X)                           |
| 单轮交换   | O(Y × (X−Y)) ≈ O(X·Y)          |
| 总交换轮数 | R（典型 R = O(X)，与 Z 无关）  |
| **合计**   | **O(X log X) + O(R·X·Y)**      |

在 X=10000、Y=1000 量级，算法可在数秒内完成。

---

## 安装与依赖

- Python 3.8+
- **内核**：仅标准库，无第三方依赖
- **Web 应用**：`pip install streamlit`

```bash
pip install -r requirements.txt
```

---

## 使用方式

### 1. 内核 API：`select_invoices`

```python
from invoice_selector import select_invoices, SolverConfig

# 列表 of (id, amount)
rows = [("FP001", 1200.50), ("FP002", 800.00), ...]
result = select_invoices(rows, select_count=4, target_amount=5000.0)

# 列表 of dict
rows = [{"id": "A001", "amount": 1000.0}, ...]
result = select_invoices(rows, select_count=3, target_amount=4000.0, id_key="id", amount_key="amount")
```

### 2. 返回结果 `SelectResult`

- `selected`：选中的发票列表
- `total_amount`：总金额
- `gap`：超出 Z 的金额
- `selected_ids`：选中发票 ID 列表
- `is_feasible()`：是否满足 ≥ Z

### 3. 配置 `SolverConfig`

- `max_swap_rounds`：最大交换轮数
- `min_improvement`：单次交换至少改善金额（元）
- `sort_descending`：是否按金额降序
- `sort_tie_break_seed`：同金额打乱种子，用于产生多种组合

---

## 项目结构

```
NP完全问题算法/
├── invoice_selector/      # 内核包
│   ├── __init__.py
│   ├── api.py             # 入口 API
│   ├── solver.py          # 排序+贪心+交换求解器
│   ├── config.py
│   └── types.py
├── main.py                # Streamlit Web 应用
├── generate_raw_data.py   # 生成 raw_data.txt
├── example.py             # 命令行示例
├── raw_data.txt           # 原始发票数据（由 generate_raw_data 生成）
├── README.md
├── DEMO.md
└── requirements.txt
```

---

## Web 应用：发票凑数神器

运行：

```bash
python main.py
```

或：

```bash
streamlit run main.py
```

支持上传发票 txt、输入 Y/Z、执行凑单、查看 Top 3 解法、分页浏览、导出 CSV。详见 [DEMO.md](./DEMO.md)。

---

## 版本

`invoice_selector.__version__` = 0.1.0
