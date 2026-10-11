# MCP 消费方接入

2026-10-11生效。正式契约为Bearer认证的Streamable HTTP `/mcp`；旧SSE优先与带project_id的query工具说明已被取代。FastMCP 3.2.0，平台锁定langchain-mcp-adapters 0.3.2，不切换beta API。

## 配置与授权

每个项目配置独立长随机token，知识服务端将其绑定tenant/project/namespace。消费方只把Bearer放在HTTP headers；模型输入只有query/top_k，不能选择scope/namespace/URL。接口参数不作为授权边界。未知/失效token HTTP401，无默认corpus回退。

平台以 `PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON` 将可信tenant:project映射到resource；Runtime `RUNTIME_MCP_CONNECTIONS_JSON` 保存resource连接、Authorization、scope、allowed_tools。新Thread由平台签发binding，Runtime核对tenant/project/thread和connection.scope后再discovery。MCP配置不能经浏览器Context/metadata/input传入。

```json
{
  "knowledge_project_a": {
    "transport": "streamable_http",
    "url": "http://127.0.0.1:8000/mcp",
    "headers": {"Authorization": "Bearer <private-token>"},
    "scope": {"tenant_id": "__default", "project_id": "11111111-1111-4111-8111-111111111111"},
    "allowed_tools": ["mcp_query_project_knowledge"]
  }
}
```

平台仅装配查询工具，管理读工具仍在MCP端同scope，但不进模型allowlist。不同连接允许同名查询；单个连接重复名字、非只读hint、保留名冲突或scope错误拒绝。

## 输出

返回单JSON文本块与同值structuredContent。status为ok/no_hit，sources字段为source_id、document_id、chunk_id、title、kind、preview、truncated。title是调用内序号+真实文件名，两个同名文件不会误合并。source_id仅标识该次检索快照，不是下载地址。

失败为isError=true，安全code为knowledge_retrieval_failed；传输错误沿消费方既有工具错误分类。取消保持CancelledError，不改写no_hit。不提供页码、正文下载、source_url或provider原始数据。

Runtime通过官方interceptor在Adapter转换前校验/投影，最多8条/800字符/12KiB。ToolMessage.artifact为 `{"structured_content": <safe-result>}`，模型正文与artifact一致。F04更小预算按完整字段缩短并同步artifact；不能截断JSON再渲染“完整来源”。后端前端消费同一检索快照，历史不重新查询。

## 维护与回退

已发布namespace不可追加；新版本完整离线入库+发布后切token→namespace并重启服务。模型名/Embedding模型/维度变更必须重建。启动会校验全部scope的ready状态和签名，失败则整个服务拒绝启动，不能偷偷回到另一项目资料。

停用先在平台项目工具策略deny查询，处理在途Run，再撤token、移除新Thread映射或停服务。只移除API映射不会撤销旧Thread binding。保留历史/语料；恢复时用仍获授权的旧namespace/resource，不做数据删除。

本地默认loopback；跨机部署由部署方提供内网/HTTPS和私有配置，不能把Bearer直接放浏览器。POSIX文件锁用于macOS/Linux单机目录，Windows部署需替代锁机制后再验收。
