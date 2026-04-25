# SLOBF: Source-Level Obfuscation Framework for Binary Similarity Research

SLOBF 是一个专为二进制相似性分析研究设计的源码级混淆框架。它能够自动化地对 C 语言源码进行语义保持的混淆，并评估其对主流深度学习二进制相似性模型的影响。

## 1. 论文目标
本项目旨在通过三个研究问题（RQ）系统地评估源码级混淆的有效性：
- **RQ1**: 不同源码级函数混淆算子对可学习二进制相似性分析模型的影响如何？
- **RQ2**: 强化学习引导的成本感知混淆组合搜索能否在混淆效果与开销之间取得更优平衡？
- **RQ3**: 编译优化级别如何影响源码级函数混淆的有效性？

## 2. 环境要求
- **操作系统**: Ubuntu 22.04 LTS (推荐) 或 WSL2 Ubuntu
- **编译器**: GCC 11.4+
- **Python**: 3.10+
- **系统依赖**: `build-essential`, `gcc-multilib`, `libmagic-dev`

## 3. 安装步骤

### WSL Ubuntu 安装
```bash
# 克隆仓库
git clone https://github.com/user/SLOBF.git
cd SLOBF

# 运行环境安装脚本
bash scripts/setup_env.sh
```

### Python 环境
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. 实验复现指南

### 数据集准备
```bash
bash scripts/download_datasets.sh
python -m slobf.cli scan --path data/raw/coreutils-9.1
```

### 运行实验
```bash
# 运行 RQ1 (单算子评估)
bash scripts/run_rq1.sh

# 运行 RQ2 (RL 组合搜索)
bash scripts/run_rq2.sh

# 运行 RQ3 (编译优化影响)
bash scripts/run_rq3.sh

# 一键运行所有实验并整理结果
bash scripts/run_all.sh --threads 8
```

## 5. 结果说明
实验结果统一保存在 `results/` 目录下：
- `results/tables/`: 论文使用的 LaTeX 表格。
- `results/figures/`: 高质量结果配图 (PDF/PNG)。
- `results/reports/`: 各 RQ 的详细分析报告。
- `results/paper_ready/`: 冻结的配置文件和环境信息，用于确保复现性。

## 6. 扩展说明
- **接入新算子**: 在 `slobf/obfuscators/` 下继承 `BaseObfuscator` 并在 `ObfuscationManager` 中注册。
- **接入新模型**: 在 `slobf/models/` 下实现 `ModelAdapter` 协议。

## 7. 常见错误 (FAQ)
- **Tigress 未找到**: 请确保已安装 Tigress 并设置 `TIGRESS_HOME` 环境变量。
- **内存不足**: 深度学习模型评测时建议至少 16GB 显存或 32GB 系统内存。
