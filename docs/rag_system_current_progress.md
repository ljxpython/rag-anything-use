# 当前知识服务能力

最后更新：2026-10-11。

已实现：固定Bearer scope与目录防逃逸；一次结构化检索；opaque文档/片段来源、安全DTO；异步engine缓存、明确LightRAG workspace；离线单写者和不可变发布；基础查询/文本入库与重型文档extra分离；CLI退出清理；HTTP/stdio契约、安全/取消测试。

测试：完整24项通过（10.42秒），覆盖协议、安全、生命周期及清理失败保留原错误/取消。

真实通过：独立Ollama nomic-embed-text768维和DeepSeek；alpha/beta不同scope索引发布、HTTP并发查询；平台11项验收包含Showcase/DearFlow两主图×两项目4条Worker链及权限/Stop/重启/fork/历史；读锁、失败发布、新版本独立token/旧索引保留和MCP/Embedding重启通过。3份合成Markdown30题（20题有答案命中20，来源越界0）。小语料结果不代表真实业务资料质量。

模型配置：miaomiaoai DeepSeek抽取使用 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`、本地8192输出预算，新版本入库复验成功；其他供应商默认 `{}`。此配置不改消费平台的默认模型或锁文件。

环境阻塞：本机Intel macOS/Python3.13无法安装锁定Torch2.11，PDF/Office Docling与多模态解析尚未实测。需兼容环境及代表性资料后补验；不修改锁来伪造兼容、不引入Docker。

前端不属于本工程：平台同事联验既有来源卡，浏览器不直连MCP、无知识CRUD产品。启动和维护见[README](../README.md)。
