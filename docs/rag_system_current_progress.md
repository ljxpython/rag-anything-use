# 当前知识服务能力

最后更新：2026-10-13。Ubuntu 分支 `feat/online-documents-20261013` 的在线文档／多模态、来源 v2、复杂文档与临时平台文档闭环验收通过；正式平台合入和部署待协同。证据以 [本期验证](projects/20261013-online-documents/verification.md) 为准，旧专项结果保留。

基础功能：固定 Bearer scope／目录防逃逸、一次结构化检索、安全来源 DTO、不可变发布／单写者；在线 SQLite 任务／hash 原件／幂等／配额／授权租约／失ACK GET；完整冻结候选、原生新增文档增量、CAS 激活、reader lease 和回退。online 默认关闭，不修改现役已发布库。

本期新增 MD／TXT 之外的 PDF／DOCX／PPTX／PNG／JPEG，按 documents 依赖与 Docling／完整多模态开关声明；真实容器校验、受管图片完整成果 hash／签名／恢复，缺损拒绝，旧快照恢复零新增模型调用；严格多模态描述失败传播、禁用 individual fallback，不标半成品 ready。默认 sources v1 保持七字段，显式 v2 从可信 native chunk 输出 page／slide／unknown，DOCX／图片不猜页。

Ubuntu 五格式独立 CLI→发布→鉴权 HTTP MCP，13 个正文／表格／公式／图片事实全过；PNG／JPEG 真模型入库／恢复／复用／reader 重启通过。RAG 119 passed，静态／frozen依赖检查通过。Intel Mac 仍缺锁定 Torch wheel，documents 应在受支持 Linux 或 ARM Mac 实测。

模型：miaomiaoai `deepseek-v4.1-flash` 文本／视觉与百炼 `text-embedding-v4`／1024；RAG-Anything1.4.2、LightRAG1.4.12、Docling2.84.0、MinerU3.4.5。当前供应商抽取 reasoning_effort:off 实测；none 在复杂节点曾400，失败 JSON 不覆盖。源码／env.example／examples 无旧供应商专用调用。

真实临时平台 union：普通成员 PDF 浏览器上传／root审批／Worker ready、另一成员新旧 MD/PDF/DOCX/PPTX 查询、撤权／Stop／Worker 重启／Fork／同hash零新增调用通过；20MiB 双页 PDF、两项目排队且旧库可查。平台主工作区未覆盖；临时补丁及正式来源展示／图片 ImageRef 收据接线见 [协同方案](projects/20261013-online-documents/platform-contract.md)。PNG/JPEG 授权为受控边界，未冒充平台图片闭环。

通用公开合成资料最终19题：16有答案召回／证据完整率1.0、跨项目来源0，裸检索P50/P95=2.948/3.564秒；三个真实Agent无答案案例拒答，检索仍可能返回无关来源。30次确定性快照锁／恢复验证不能外推生产吞吐；费用金额null，生产 SLA／私有业务门槛未提供。音视频用户暂不开发，见 [剩余事项](remaining-work.md)。
