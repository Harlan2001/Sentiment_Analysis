# 模型目录说明

本目录用于存放项目运行所需的本地模型文件。

## 一、模型列表

1. `models/all-MiniLM-L6-v2/`
   - 来源: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
   - 当前向量库和相似度代码默认使用该目录名。
   - 相关代码: `backend/vector_store.py`、`backend/factor_similarity.py`
   - 至少应包含:
     - `config.json`
     - `model.safetensors`
     - `tokenizer.json`（或 `tokenizer_config.json`）
   - 可一并保留仓库页面自带的 `README.md`、`.gitattributes`

2. `models/text2vec-base-chinese/`
   - 来源: https://huggingface.co/shibing624/text2vec-base-chinese
   - 仅在需要切换中文向量模型时下载。
   - 当前代码注释提到该模型，但默认加载并不是它。

## 二、推荐下载方式

推荐使用 Hugging Face CLI 下载到固定目录。

### 1. 安装工具

```powershell
pip install -U "huggingface_hub[cli]"
```

### 2. 下载模型

在项目根目录执行：

```powershell
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir models/all-MiniLM-L6-v2
```

如果需要中文向量模型，再执行：

```powershell
huggingface-cli download shibing624/text2vec-base-chinese --local-dir models/text2vec-base-chinese
```

如果内网无法直接访问 Hugging Face，可先设置镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

## 三、目录命名要求

必须保持如下结构，不能多一层嵌套目录：

```text
models/
├── all-MiniLM-L6-v2/
│   ├── config.json
│   └── model.safetensors
```

错误示例：

```text
models/
└── all-MiniLM-L6-v2/
    └── sentence-transformers/all-MiniLM-L6-v2/
```

## 四、Git 约定

1. `models/` 下的模型文件只保留在本地，不提交到 Git。
2. 目录名必须保留，便于团队成员按文档统一放置模型。
3. 如需更新模型版本，只更新本地文件和本说明，不要直接把大模型文件提交进仓库。
