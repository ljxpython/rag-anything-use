# 本期实施记录与 Task Completion Card

## U01

保留 Ubuntu env.example 原修改和 hash 后正常更新 main，保留私有配置与知识库，在 feat/online-documents-20261013 开发；版本锁未再改动。

## D01／D02

`src/knowledge/document_formats.py` 统一能力声明及真实 PDF／Office／图片容器校验；`upload_service.py` 在授权字节上传后验证，保持流式 hash 与配额。`artifacts.py` 保存带完整 checksum／signature 的 content-list 和受管图片，hash／大小／格式逐项校验，临时路径替换为受管引用。`generations.py` 复用原候选增量链，旧快照激活／读恢复前校验成果和资产，缺损拒绝，不解析旧文档。

`demo_support.py` 校验每个多模态描述的详细正文和实体字段，完整 batch 才允许完成；禁用上游失败后 individual fallback，避免半写入被误记成功。`rag_engine.py` 为纯多模态补齐文档存储与真实 chunks 绑定。接口异常保持公开 knowledge_processing_failed，详细原因写私有日志。

供应商 reasoning_effort:none 在后续节点出现 400；miaomiaoai 当前实测支持 off，私有配置和 env.example 使用 off。五格式最终独立复跑全通过，13 事实命中；PNG／JPEG 真实模型入库、复用、reader 重启通过。首次失败不覆盖，证据均在 evidence/。

## C01

`parser_adapter.py`／`content_normalizer.py` 保留可信页范围，`KnowledgeRAGAnything` 传播跨页上界。`citations.py`／`schemas.py`／`rag_engine.py`／`mcp_server.py` 增加显式 sources_version=2，从绑定 native chunk 输出 page／slide／unknown，默认 v1 七字段保持兼容。单页、跨页、布尔或逆序拒绝、未知、DOCX／图片无固定页码均有回归。

平台正式 v2 接线方案和后续 ImageRef 收据说明见 platform-contract.md。本轮平台保持 v1。

## V01

临时 union 基于包含既有 Token／后台功能的 06d94130，并组合原知识 worktree。最小联验修复见平台 patch；主工作区未覆盖，临时 union staged 原知识内容未提交。

真实普通成员 PDF 上传、root 审批、input.respond 恢复、Worker 入库、浏览器项目面板已可检索、另一成员新旧查询通过。DOCX／PPTX、重复 hash 零新增调用、撤权、Stop、Worker 重启与 Fork 全有真实证据；CAS／回退与资产损坏拒绝在 RAG 全套回归验证，不伪称通过浏览器操作管理员接口。

## Q01

公开 API／运维／发布资料 19 题最终独立复跑，16 道有答案 recall@8／证据完整率 1.0，跨项目来源 0；三个 Agent 无答案案例拒答。20MiB 合法双页 PDF 与两项目排队，旧查询不中断；30 次确定性快照的旧校验和不变、恢复零新增模型、close 后共享键归零。真实模型负载规模和供应商 429 写明，不外推生产容量。

## F01

最终 RAG 119 passed；相关平台、Token／后台及 Web 回归与 typecheck 通过，显式跳过项单列。变更 16 个 Python 文件 ruff format／check、compileall、frozen lock 与 pip check 通过；交付只包含源码、测试、脱敏证据、补丁和文档。原始私有日志不入库。最终停服与远端分支信息写入 verification.md／delivery.json。
