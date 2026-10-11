# 知识服务运行与更新

当前启动/参数以[README](../README.md)和[消费契约](mcp_receiver_integration_guide.md)为准。离线UTF-8文本→LightRAG索引→发布→Streamable HTTP是首版主链，管理员CLI之外没有在线写接口。

## 首次启动

1. 独立目录安装锁定环境；`uv sync --frozen --group dev`。
2. 配置LLM、Ollama Embedding、root和token scopes，私有env权限600。
3. `main.py ingest --project-id <namespace> --file <文本文件>`逐份入库，检查全部ready。
4. `main.py publish --project-id <namespace>`冻结索引；MCP启动前要求发布标记、manifest、rag目录、模型签名一致。
5. `uv run --frozen --env-file <private-env> python src/mcp_server.py`。只监听登记的本环境loopback端口。
6. 消费方Bearer discovery+query，再联验平台Thread/Worker/历史。stdio不能代替HTTP验证。

miaomiaoai `deepseek-v4.1-flash` 的本地抽取配置为 `LLM_MAX_TOKENS=8192`、`LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`；曾因没有正文导致索引失败，补配置后新版本导入成功。其他供应商不支持该参数时用 `{}`，不是任意模型的通用开关。

## 更新

用新namespace导入全部应公开资料，全部ready后发布。未发布/失败不影响旧namespace。切scope到新版本并重启MCP，验证后再对新Thread配置/旧Thread可达resource作对应更新。回到旧版本前确认旧资料仍被允许保留/访问；撤回敏感资料不能通过回退重新授权。

不要原地替换已发布文件、manifest、向量或模型。MCP持共享锁，入库CLI独占锁，运行中写同namespace立即失败。manifest采用原子替换，不靠文件名猜引用。query缓存可能落盘，启动/关闭由engine负责；语料与索引只由离线管理员写。

## 故障

- 401：核对当前项目token/scopes；不传project参数尝试绕过。
- namespace未发布/签名不匹配/manifest损坏：恢复受控原配置或重建新版本，不生成公共库。
- knowledge_retrieval_failed：查私有日志，公开响应不提供路径/供应商异常；最多60秒检索deadline。
- 入库失败：CLI exit1，失败记录不能发布；保留证据，在新namespace重新导入。
- PDF/Office：需要 `--extra documents`，Intel macOS锁定Torch无wheel；提供兼容ARM/Linux环境后复验。多模态没有作为本机已通过能力。

平台Worker Stop阻止迟到结果写入已结束Run；外部LLM/Embedding已提交请求可能继续，不能保证远端费用立即归零。

2026-10-11 已真实验证读锁拒写、空文本失败不可发布、模型签名改变拒绝、新版本独立token/旧token401及旧索引保留、MCP与独立Ollama重启后来源相同。平台本地资源统一由其 `scripts/local-stack.sh` 的knowledge登记/启停管理；端口/PID不手工接管其他环境。精确环境与安全证据见消费平台本次专项部署手册。
