# 当前知识服务能力

最后更新：2026-10-12。

已实现：固定Bearer scope与目录防逃逸；一次结构化检索；opaque文档/片段来源、安全DTO；异步engine缓存、明确LightRAG workspace；离线单写者和不可变发布；逻辑项目SQLite任务/幂等；原件流式hash、受管票据和配额；完整快照恢复到独立候选、原生新文档增量、原子激活/读lease/回退；online MCP提交/状态和内部HTTP（默认关闭）；CLI注册/迁移/回退；用量阶段计数与安全错误。

测试：RAG完整78项通过（52.28秒），覆盖协议、安全、生命周期、增量/计数、迁移/回退、子进程故障/缓存回收与后台授权/失ACK私有回查。

真实通过：隔离真实DeepSeek + 百炼兼容text-embedding-v4/1024维的HTTP/MCP/worker链；恢复/重复A零新增入库usage，A/B图抽取和Embedding阶段归类，回退searchable与旧checksum不变；父SIGKILL子进程回收、重启恢复和10次mock发布 workspace 回收通过。平台生产IAM/Runtime、前端、Linux格式、代表性业务质量/负载尚未验收；小语料不代表业务资料质量。

实际平台授权追加验收：完整后台请求start/activate200；签名篡改/过期/撤权拒绝；受理后Thread删除任务仍完成；同key GET在新写暂停后仍返回同安全回执且不增attempt/usage。采用实际Platform API源码＋隔离SQL主体，非Runtime Agent/浏览器完整验收；见 [证据](projects/20261012-rag-provider-contract-alignment/verification.md)。

模型配置：miaomiaoai DeepSeek抽取使用 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`、本地8192输出预算，新版本入库复验成功；其他供应商默认 `{}`。此配置不改消费平台的默认模型或锁文件。

环境阻塞：本机Intel macOS/Python3.13无法安装锁定Torch2.11，PDF/Office Docling与多模态解析尚未实测。需兼容环境及代表性资料后补验；不修改锁来伪造兼容、不引入Docker。

前端不属于本工程：平台同事联验既有来源卡，浏览器不直连MCP、无知识CRUD产品。启动和维护见[README](../README.md)。
