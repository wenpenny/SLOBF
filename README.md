# SLOBF: Source-Level Obfuscation Framework for Binary Similarity Research

SLOBF 是一个专为二进制相似性分析研究设计的**函数级**源码混淆框架。基于 tree-sitter AST 精确变换，对 C 语言函数进行语义保持的混淆，并评估其对主流深度学习二进制相似性模型的影响。

## 1. 混淆算子

| 算子 | 全称 | 混淆方式 |
|------|------|---------|
| **OPI** | Opaque Predicate Insertion | 用数学恒等式（恒真/恒假）谓词将语句包进 if-else |
| **CFF** | Control Flow Flattening | 将 if/for/while 拆成基本块，用 while-switch 调度器统一控制 |
| **ER** | Expression Rewriting | 将算术/逻辑表达式替换为代数等价形式（如 `a+b` → `a-(-b)`） |
| **DE** | Data Encoding | 将整数常量、字符串字面量 XOR 编码，编译时隐藏原值 |
| **JCI** | Junk Code Insertion | 插入无副作用的 volatile 变量、位运算、死循环等垃圾代码 |
| **FS** | Function Splitting | 将函数从中间切分为原函数 + static helper，增加调用图复杂度 |

所有算子均基于 tree-sitter 解析 AST，通过 byte-offset 精确替换，保证编译通过、运行结果不变。

## 2. 论文目标

三个研究问题（RQ）：
- **RQ1**: 单个源码级混淆算子对二进制相似性模型的影响
- **RQ2**: 强化学习引导的代价感知混淆组合搜索
- **RQ3**: 编译优化级别（O0-O3）对混淆有效性的影响

## 3. 环境要求

- **操作系统**: Ubuntu 22.04 LTS（推荐）或 Windows + MinGW-w64
- **编译器**: GCC 11.4+
- **Python**: 3.10+
- **系统依赖**: `build-essential`, `gcc-multilib`

## 4. 安装

```bash
git clone https://github.com/wenpenny/SLOBF.git
cd SLOBF
bash scripts/setup_env.sh
source venv/bin/activate
```

## 5. CLI 命令一览

```bash
# 扫描数据集，提取函数
slobf scan

# 对单个函数施加混淆，保存源码
slobf obfuscate --operator OPI --function func_name \
  --source path/to/file.c --output path/to/result.c

# 查看所有可用的混淆算子
slobf obfuscate --help

# 编译完整 C 程序（可指定修改后的源文件）
slobf compile --program path/to/program --opt O0

# 从 ELF 二进制提取函数
slobf extract --binary path/to/program.elf --function func_name

# 语义等价验证：编译运行原版和混淆版，对比输出
slobf verify --original src.c --obfuscated obf.c --function func_name

# 运行实验
slobf rq1           # RQ1: 单算子评估
slobf rq2           # RQ2: RL 组合搜索
slobf rq3           # RQ3: 编译优化影响
slobf sanity-check  # 生成论文图表
```

## 6. 实验复现

```bash
# 1. 下载并准备数据集
bash scripts/download_datasets.sh
slobf scan

# 2. 分别运行三个实验
bash scripts/run_rq1.sh
bash scripts/run_rq2.sh
bash scripts/run_rq3.sh

# 3. 生成论文图表
slobf sanity-check

# 或一键运行
bash scripts/run_all.sh
```

## 7. 结果目录

```
results/
├── rq1/                  # RQ1 结果
│   ├── single_operator_raw.csv
│   └── summary_by_operator.csv
├── rq2/                  # RQ2 结果
│   └── rl_eval_raw.csv
├── rq3/                  # RQ3 结果
│   └── optimization_raw.csv
├── tables/               # LaTeX 表格
├── figures/              # 论文配图
└── paper_ready/          # 环境快照（复现用）
```

## 8. 扩展

- **接入新算子**: 在 `slobf/obfuscators/` 下继承 `BaseObfuscator`，在 `ObfuscationManager` 中注册
- **接入新模型**: 在 `slobf/models/` 下实现 `ModelAdapter` 协议

## 9. 已知局限

- CFF 不处理 `do-while` 循环（语义保持，但循环体不会被展平）
- ER 不处理三元运算符 `?:` 和函数调用表达式
- DE 不编码浮点字面量（浮点编码语义复杂）
- FS 要求函数有且仅有一个 `return` 语句
- 所有算子假定 GCC 可编译的标准 C（部分字符串编码使用 GCC extension）

## 10. 常见问题

- **内存不足**: 深度学习模型评测时建议至少 16GB 显存或 32GB 系统内存
- **函数未找到**: `slobf obfuscate` 需先用 `slobf scan` 扫描生成函数清单，或确认函数名正确
- **混淆后编译失败**: 确认 GCC 版本 ≥ 11.4，部分编码使用 `__extension__` 需要 GCC
