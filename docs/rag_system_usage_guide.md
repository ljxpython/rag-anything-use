# 知识服务运行与更新

当前启动/参数以[README](../README.md)和[消费契约](mcp_receiver_integration_guide.md)为准。离线UTF-8文本→LightRAG索引→发布→Streamable HTTP是稳定主链；online逻辑库的受管异步入库默认关闭；基础MD/TXT，完整documents配置下另支持PDF／DOCX／PPTX／PNG／JPEG，必须配置平台精确授权和迁移后的 `knowledge_base_id`。

## 首次启动

1. 独立目录安装锁定环境；`uv sync --frozen --group dev`。
2. 配置LLM、Ollama Embedding、root和token scopes，私有env权限600。
3. `main.py ingest --project-id <namespace> --file <文本文件>`逐份入库，检查全部ready。
4. `main.py publish --project-id <namespace>`冻结索引；MCP启动前要求发布标记、manifest、rag目录、模型签名一致。
5. `uv run --frozen --env-file <private-env> python src/mcp_server.py`。只监听登记的本环境loopback端口。
6. 消费方Bearer discovery+query，再联验平台Thread/Worker/历史。stdio不能代替HTTP验证。

online 启用前由管理员执行 `init-project-knowledge`、完整旧库 `migrate-project-knowledge` 和 `activate-knowledge-generation --uploads on`；旧服务必须先释放legacy namespace读锁。在线上传不接受浏览器直传、URL或宿主路径，平台 Runtime 负责可信附件核对和内部 PUT。完整命令、headers、HMAC canonical规则和回退步骤见 [RAG接线交接](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)。

miaomiaoai `deepseek-v4.1-flash` 的本地抽取配置为 `LLM_MAX_TOKENS=8192`、`LLM_EXTRA_BODY_JSON='{"thinking":{"type":"disabled"},"reasoning_effort":"off"}'`；当前供应商 off 完整五格式复跑通过，none 曾在复杂节点400。外部供应商仍可能限流，最终质量复跑两次Embedding429已重试恢复。其他供应商不支持该参数时用 `{}`，不是任意模型的通用开关。

## 更新

offline 更新仍用新namespace导入全部应公开资料，全部ready后发布。online 更新由单worker从最新完整active快照恢复到独立候选，只处理新文档和受影响图数据；未发布/失败不影响旧视图，成功后SQL原子切换并由读lease保护在途查询。回退先关闭上传，再激活完整旧generation；不删除原件和版本。

不要原地替换已发布文件、manifest、向量或模型。MCP持共享锁，离线CLI/online builder独占锁，运行中写同namespace立即失败。manifest采用原子替换，不靠文件名猜引用；online builder持独立候选，子进程只构建不激活。query缓存可能落盘，启动/关闭由engine负责。

## 故障

- 401：核对当前项目token/scopes；不传project参数尝试绕过。
- namespace未发布/签名不匹配/manifest损坏：恢复受控原配置或重建新版本，不生成公共库。
- knowledge_retrieval_failed：查私有日志，公开响应不提供路径/供应商异常；最多60秒检索deadline。
- 入库失败：CLI exit1或online job=failed，失败记录不能发布；保留原件/证据，明确新提交才重试，旧key不隐式重试。
- PDF／Office／图片：安装 `--extra documents`，`PARSER=docling` 且 image/table/equation 三开关启用；Ubuntu五格式13事实与PNG/JPEG真实模型入库／恢复通过。完整模型缓存可开HF_HUB_OFFLINE=1；Intel Mac锁定Torch无wheel。平台ImageRef图片可信链仍待接入，不能按path伪造FileRef；见[本期验证](projects/20261013-online-documents/verification.md)。

视觉配置改变会影响online处理签名，即使文本模式没有调用视觉接口；不得更改签名来继续复用旧库。部署切换需独立新库／候选验证。本次在独立Ubuntu分支完成文档／资产／定位及临时平台联验；现役索引不切换，正式平台合入与部署见[剩余事项](remaining-work.md)。

RAG-Anything升级至1.4.2后，online文本签名不再受未使用的解析依赖安装影响；仅精确允许已核验v1文本组合，模型/端点/维度/分块变化仍拒绝旧索引。发布索引不原地改ID或表格内容；需要来源修复/紧凑表格收益的旧离线库必须用原件导入独立新namespace。

平台Worker Stop阻止迟到结果写入已结束Run；外部LLM/Embedding已提交请求可能继续，不能保证远端费用立即归零。

2026-10-12 已真实验证完整快照恢复/原生增量、实际usage阶段归类、失败候选不污染旧视图、回退、在线worker/HTTP/MCP、重复零新增usage、父SIGKILL子进程回收和连续发布缓存回收；平台本地资源统一由其 `scripts/local-stack.sh` 的knowledge登记/启停管理，本期临时union真实IAM／Runtime Worker文档闭环已通过，正式平台合入部署另行实施。端口/PID不手工接管其他环境。精确证据见专项 [RAG实施验收](projects/20261012-project-member-knowledge-upload/implementation/rag-evidence.md)。
