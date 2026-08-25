# 飞书 MCP 首期配置

## 1. 配置环境变量

在部署环境中设置以下值。`FEISHU_APP_ID`、`FEISHU_APP_SECRET` 可继续使用现有飞书推送应用的凭证；但该应用还需要在飞书开放平台开启 OAuth 回调和下述只读权限。

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_OAUTH_REDIRECT_URI=https://your-domain.example/sapi/mcp/feishu/callback
FEISHU_TOKEN_ENCRYPTION_KEY=base64-url-safe-fernet-key
```

生成令牌加密密钥：

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`FEISHU_OAUTH_REDIRECT_URI` 必须与飞书开放平台中填写的回调地址完全一致。不要将 App Secret 或 Fernet 密钥暴露给浏览器。

## 2. 飞书应用配置

创建或更新企业自建应用，启用网页 OAuth，并在权限管理中按最小权限申请以下**读取**能力：

- 云文档搜索与读取；
- 多维表格元数据与记录读取；
- 群组信息读取；
- 群消息读取。

不同租户的飞书管理员审批策略不同；如果群消息历史读取未获批准，其他已授权的文档和表格工具仍可继续使用。

## 3. 部署与验证

应用启动时会自动创建 `workbench_feishu_*` 数据表。打开“自定义 → MCP”，飞书应位于第一张卡片；点击“连接”并完成飞书授权后，状态将变为“已连接”。

首期工具全部只读：

- `search_feishu_docs`
- `get_feishu_doc_content`
- `get_bitable_metadata`
- `list_bitable_records`
- `list_feishu_chats`
- `list_feishu_messages`

这些工具既可通过 `/sapi/mcp/feishu/tools/{tool_name}` 调用，也已注册给对话 Agent。每次执行都会记录审计日志，且只使用当前登录用户的飞书 OAuth 令牌。
