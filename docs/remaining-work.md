# 剩余开发与验收事项

最后更新：2026-10-13。本次已在 sshmy2 完成 RAG 在线文档、多模态资产、来源 v2、复杂文档稳定性和通用质量／负载验证；临时平台真实闭环已通过。任务与证据见 [本期专项](projects/20261013-online-documents/README.md)，旧升级与供应商清理结果继续保留。

## 本次已补齐

| 事项 | 当前结果 |
|---|---|
| online PDF／DOCX／PPTX／PNG／JPEG | RAG 原件校验、受管资产清单／hash、成果签名、完整恢复、候选增量／回退完成；默认不开生产上传 |
| 复杂文档稳定性 | 文本／扫描／混合 PDF、DOCX、PPTX 五格式最终全通过，13 个正文／表格／公式／图片事实命中；失败严格传播、禁止 half-ready 与 individual fallback |
| 页码／跨页来源 | RAG 显式 sources_version=2 已实现；PDF page／PPTX slide／其余 unknown，来源仅由可信 native chunk 确定；默认 v1 七字段兼容 |
| 平台 V02 文档链 | 临时 union 的真实普通成员 PDF 上传／root 审批／Worker ready／浏览器、DOCX／PPTX、另一成员旧新查询、撤权／Stop／重启／Fork／同 hash 零新增调用通过 |
| 通用检索质量 | 用户选定公开合成资料 19 题最终复跑，16 有答案 Recall@8 和证据完整率 1.0，跨项目来源 0；三个真实 Agent 无答案场景拒答 |
| 当前资源负载 | 20MiB 合法双页 PDF、两个项目排队且旧库可查、30 次确定性快照与锁／共享键回收通过；当前 Ubuntu 4 核、约 3.6GiB RAM，无本地 GPU 需求 |

## 仍需实施／协同

| 事项 | 具体剩余内容 | 原因与下一步 |
|---|---|---|
| 平台正式合入与部署 | 合并已有知识专项基线和本次 12 文件临时修复；保留 Token 看板／后台回执与迁移身份；正式 frozen 回归后部署 | 本轮用户要求平台方案及真实联验，临时 union 未直接合入主工作区；已交付 [补丁](projects/20261013-online-documents/platform-integration.patch) 与 [基线说明](projects/20261013-online-documents/platform-patch-context.json)，不能盲目套用到主线 |
| 平台来源 v2 展示 | Runtime v2 DTO／预算投影、interceptor 固定版本、Web 页／幻灯片标签、历史／Fork 兼容 | RAG v2 已完成，平台仍用默认 v1；具体文件／契约／灰度回退见 [方案](projects/20261013-online-documents/platform-contract.md) |
| 平台图片 ImageRef 可信链 | 原始上传的 name／MIME／size／hash 收据、精确知识提交转换、Web 图片共享门禁、真实 PNG／JPEG 浏览器链 | ImageRef 与 FileRef 是不同可信链；不得按 path 伪造 FileRef。RAG 图片已验，平台治理范围需按方案评审后实现 |
| 私有业务与生产 SLA | 真实业务语料／失败集，目标并发／吞吐／延迟／预算和历史保留策略 | 用户本期选择通用公开样本，当前结论只覆盖选定规模；20MiB 边界文件为双页 PDF，不等于同字节密集文档或生产容量上限 |
| 音频／视频 | ASR、时间戳／关键帧、资产、费用和失败恢复 | 用户明确暂不开发，deferred；不安装／开放该栈 |

无答案检索仍可能返回无关来源，本次真实 Agent 拒答并保留证据；不能把检索命中等同有足够答案。最终质量复跑观察到两次 Embedding 429，现有策略恢复，供应商并发配额会影响生产负载。费用没有完整可核验费率，金额保留 null。

## 环境和配置

RAG 开发已完成，2026-10-13 经用户批准将验收分支快进合入 `main`；本地 `/Users/lijiaxin/PyCharmMiscProject/rag-anything-use` 和 Ubuntu `/home/ubuntu/PyCharmMiscProject/rag-anything-use` 统一跟踪 `origin/main`，平台同事从 `main` 读取交接文档。合入后 Ubuntu 全套119项通过；你无需亲自在 Ubuntu 补代码。Intel Mac 缺锁定 Torch wheel，Ubuntu 用于实际 Docling／PDF／Office 解析；平台代码／契约开发可在 Mac，图片或 Office 端到端联合 Ubuntu 解析服务验证。私有 `.env`、依赖和知识库按环境保留，不纳入 Git 同步。

文本／视觉统一 miaomiaoai `deepseek-v4.1-flash`，Embedding 为百炼 `text-embedding-v4`／1024；源码、examples 和 env.example 已移除旧供应商。当前供应商抽取用 reasoning_effort:off，none 曾返回 400；更换模型／维度／视觉／处理签名用新库候选验证，不修改旧签名绕过校验。

现役服务／历史索引未迁移或启用新增上传。早前 env 解析警告曾回显一个旧 MCP token，值未写入文档或证据；现役启服前仍需和消费方协调轮换。本次隔离联验使用独立配置，不替换现役凭据。
