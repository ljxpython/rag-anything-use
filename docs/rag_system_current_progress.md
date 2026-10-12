# 当前知识服务能力

最后更新：2026-10-13；用户验收升级与本期优化范围通过，需求done，登记的本地知识服务已停。

已实现：固定Bearer scope与目录防逃逸；一次结构化检索；opaque文档/片段来源、安全DTO；异步engine缓存、明确LightRAG workspace；离线单写者和不可变发布；逻辑项目SQLite任务/幂等；原件流式hash、受管票据和配额；完整快照恢复到独立候选、原生新文档增量、原子激活/读lease/回退；online MCP提交/状态和内部HTTP（默认关闭）；CLI注册/迁移/回退；用量阶段计数与安全错误。

本轮已升级RAG-Anything 1.4.2 / MinerU 3.4.5，保留LightRAG 1.4.12 / Docling 2.84.0；修复同正文多来源chunk覆盖、解析tuple/参数/页码、真实chunk计数、紧凑表格表示、首解析缓存、多模态workspace绑定、batch/fallback资产路径脱敏和CLI失败退出码。旧在线文本签名精确兼容已核验v1组合，不重写冻结快照。

最终测试：2026-10-13合并主线授权/失ACK修复后，Ubuntu107项通过（25.32秒）；Intel Mac101项通过、6项documents跳过（169.36秒）。合并前升级分支的96/90项日志保留为历史证据，见[专项证据](projects/20261012-rag-optimization/implementation/README.md)。

真实通过：sshmy2隔离DeepSeek + 百炼text-embedding-v4/1024维的HTTP/MCP/worker链，重复零新增usage、回退可查、旧checksum不变。19题公开通用资料评测16道有答案题Recall@8/证据完整率100%，跨项目来源0；3道无答案题仍返回资料。100小文档确定性快照观测与关闭共享键归零通过；生产IAM/Runtime、前端、真实业务质量/负载未联合验收。

实际平台授权追加验收：完整后台请求start/activate200；签名篡改/过期/撤权拒绝；受理后Thread删除任务仍完成；同key GET在新写暂停后仍返回同安全回执且不增attempt/usage。采用实际Platform API源码＋隔离SQL主体，非Runtime Agent/浏览器完整验收；见 [证据](projects/20261012-rag-provider-contract-alignment/verification.md)。

模型配置：miaomiaoai DeepSeek抽取使用 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`、本地8192输出预算，新版本入库复验成功；其他供应商默认 `{}`。此配置不改消费平台的默认模型或锁文件。

格式：Ubuntu文本PDF和扫描PDF最新CLI→发布→MCP通过；DOCX/PPTX初轮正文通过，最新DOCX与混合PDF各600秒超时、PPTX空正文失败。混合PDF紧凑表格修复有确定性回归，真实模型链路未通过；修正后的格式脚本未再全跑。旧iflow凭据被434拒绝；2026-10-13miaomiaoai DeepSeek两个图片HTTP探针与项目vision适配器通过，可复用LLM端点/模型/凭据配置VISION，未改现役环境。完整文档格式能力仍partial。online保持MD/TXT；Intel Mac仍无法安装锁定Torch2.11，ARM Mac本轮未实测。

前端不属于本工程：平台同事联验既有来源卡，浏览器不直连MCP、无知识CRUD产品。启动和维护见[README](../README.md)。
