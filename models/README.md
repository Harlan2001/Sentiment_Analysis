# 模型目录说明

本目录用于存放项目运行所需的本地模型文件。

## 一、必须下载的模型
1. `models/Kronos-small/`
   - 来源: https://huggingface.co/NeoQuasar/Kronos-small
   - 至少应包含:
     - `config.json`
     - `model.safetensors`
   - 可一并保留仓库页面自带的 `README.md`、`.gitattributes`

2. `models/Kronos-Tokenizer-base/`
   - 来源: https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base
   - 至少应包含:
     - `config.json`
     - `model.safetensors`
   - 可一并保留仓库页面自带的 `README.md`、`.gitattributes`

以下模型不是 Kronos 预测主链路的必需项，但在语义向量和相似度功能中会用到：

3. `models/all-MiniLM-L6-v2/`
   - 当前向量库和相似度代码默认使用该目录名。
   - 相关代码: `backend/vector_store.py`、`backend/factor_similarity.py`

4. `models/text2vec-base-chinese/`
   - 仅在需要切换中文向量模型时下载。
   - 当前代码注释提到该模型，但默认加载并不是它。

## 二、推荐下载方式

推荐使用 Hugging Face CLI 下载到固定目录。

### 1. 安装工具

```powershell
pip install -U "huggingface_hub[cli]"
```

### 2. 下载必需模型

在项目根目录执行：

```powershell
huggingface-cli download NeoQuasar/Kronos-small --local-dir models/Kronos-small
huggingface-cli download NeoQuasar/Kronos-Tokenizer-base --local-dir models/Kronos-Tokenizer-base
```

如果需要语义向量相关功能，再执行：

```powershell
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir models/all-MiniLM-L6-v2
```

如果内网无法直接访问 Hugging Face，可先设置镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

## 四、目录命名要求

必须保持如下结构，不能多一层嵌套目录：

```text
models/
├── Kronos-small/
│   ├── config.json
│   └── model.safetensors
├── Kronos-Tokenizer-base/
│   ├── config.json
│   └── model.safetensors
```

错误示例：

```text
models/
└── Kronos-small/
    └── NeoQuasar/Kronos-small/
```

## 五、本地加载配置

如果希望项目严格从本地目录加载模型，不依赖远程下载，请修改 `live_prediction/config/model.yaml` 为本地路径：

```yaml
model:
  name: "models/Kronos-small"
  tokenizer: "models/Kronos-Tokenizer-base"
  local_files_only: true
```

说明：当前默认配置仍是 Hugging Face 仓库名；只有改成上述本地路径后，才会强制使用本目录中的模型文件。

## 六、Git 约定

1. `models/Kronos-small/` 和 `models/Kronos-Tokenizer-base/` 只保留在本地，不提交到 Git。
2. 目录名必须保留，便于团队成员按文档统一放置模型。
3. 如需更新模型版本，只更新本地文件和本说明，不要直接把大模型文件提交进仓库。