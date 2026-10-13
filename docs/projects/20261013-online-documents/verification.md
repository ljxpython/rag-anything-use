# 验证记录

## Phase 验证

### U01：Ubuntu pull 与开发环境

2026-10-13 Ubuntu 原 main@6873035 落后主线；env.example 原修改保存到 `/home/ubuntu/.local/state/rag-anything-use/pre-pull-20261013/env.example` 并核对 hash 后，仅恢复该文件、ff-only 拉取到 edd7963。私有 .env、知识库保留。在 `feat/online-documents-20261013` 安装 frozen documents；RAG-Anything 1.4.2／LightRAG 1.4.12／Docling 2.84.0／MinerU 3.4.5，Python 3.13.16。

### D01：复杂格式与多模态稳定性

首次与中间失败见 `evidence/formats-before.json`、`formats-after.json`、`final-offline/formats.json`。早期有空正文／超时；只传 thinking.disabled 仍有 reasoning，reasoning_effort:none 在后续 DOCX equation 节点返回 400，不覆盖失败结果。当前供应商 off 实测返回正文且 reasoning tokens 0（`provider-off.json`）；env.example 与私有配置同步 off。

最终独立新 namespace、已缓存 Docling 模型且 HF_HUB_OFFLINE=1 的完整 CLI 入库→发布→鉴权 HTTP MCP 结果见 [final-offline-off/formats.json](evidence/final-offline-off/formats.json)：

| 格式 | 状态 | 事实数 | 解析内容 |
|---|---|---|---|
| 文本 PDF | done | 2/2 | 正文，跨页范围 |
| 扫描 PDF | done | 1/1 | OCR 正文 |
| 混合 PDF | done | 3/3 | 正文、表格 |
| DOCX | done | 4/4 | 正文、表格、公式、图片 |
| PPTX | done | 3/3 | 正文、图片 |

五类 ingest/publish 退出码为 0，analysis_failures=0，individual_fallbacks=0，all_chunks_registered=true，chunk_sources_valid=true，local_asset_paths_hidden=true。13 个问题同时验证必要表格／公式／图像事实，不以 doc ready 代替内容验收。

### D02／C01：在线受管资产与来源定位

原件容器、20MiB、MIME／hash、Office 路径穿越／zip 限制、缺损受管图片、完整成果 checksum 与签名、恢复／失败候选、跨项目／重复／CAS／回退／reader lease 的自动回归包含在本轮全套 tests。

[images-real.json](evidence/images-real.json)：PNG／JPEG 使用实际 DeepSeek vision 和百炼 1024 维 embedding 入库、检索、受管资产恢复通过；同 hash 新模型调用 0，reader 重启新模型调用 0。授权边界是受控 fixture，明确不是平台 ImageRef 浏览器端到端。

来源默认 v1 不变；v2 从同文档已绑定 native chunk 读取 PDF page／PPTX slide，逆序／布尔／缺失／跨文档定位拒绝，DOCX／图片为 unknown，跨页上界和块类型有回归。RAG 已实现，平台本轮继续 v1；正式 v2 DTO 和 Web 展示方案在 [platform-contract.md](platform-contract.md)。

### V01：真实平台联合闭环

临时平台 union 基于平台主功能 06d94130，与原知识实现组合，专属 PostgreSQL／Redis／Workspace／Worker；RAG 是 Ubuntu 单服务，通过所属 SSH 隧道相互可达。Web/API/Runtime/Redis 登记端口分别 24354／26124／27507／23670；未覆盖平台主工作区。

真实普通成员浏览器 PDF 上传→共享勾选→root HITL→公开 input.respond 恢复→实际 Worker→queued/searchable=false→ready/true。MD／DOCX／PPTX 同链入库，另一成员实际 query 新旧资料。浏览器 route-list 无 mock，最终资料列表见 [截图](evidence/platform/browser-documents-final.png) 和 [回执](evidence/platform/browser-off-pdf-ready.json)。

- [Agent 验收](evidence/platform/agent-acceptance.json)：旧 MD／新 PDF、DOCX 表格／公式、PPTX 发布／回退信息、三类无答案、alpha/beta 隔离。每题均一次实际知识工具且 run success。
- [撤权](evidence/platform/real-member-revocation.json)：资料／任务／thread state／run.start 均 project_role_missing，新增入库模型调用 0。
- [生命周期](evidence/platform/lifecycle.json)：Stop 后无迟到工具结果；真实 Worker 重启、Fork 历史来源一致且再查询成功。
- [重复](evidence/platform/real-duplicate-counts.json)：ready 同 hash 复用，usage 270→270，新增调用 0。处理中幂等／失ACK／CAS／回退由 RAG 单元及 HTTP 回归验证，未伪称由浏览器管理员接口执行。

临时联验修复：动态能力／选项清理、六字段 FileRef 投影到模型正文、pending 回执“尚未受理”、root ToolNode namespace 精确校验、循环导入、迁移 head 测试与临时重复 credential_id。正式平台合入需保护主功能和 migration 身份；12 文件补丁与基线说明已交付，原知识 staged 改动未提交。

### Q01：通用质量、边界与负载

用户选择通用公开资料。本次为公开可复跑的合成 API／运维／发布规范与文档格式样本，不包含私有业务数据。

最终配置独立复跑 [quality-final.json](evidence/quality-final.json)：19 题中 16 有答案题 recall@8=1.0、evidence_completeness=1.0、cross_project_sources=0；检索 P50=2.948s，P95=3.5635s。排序与截断逐题保留。3 无答案题仍返回无关来源；服务只返回证据，不自行生成答案。真实 Agent 价格／成立年份／地址三个案例均明确拒答，alpha 来源没有 beta 的 999／DECOY-9281，beta 实际可检索该诱饵。复跑记录 166 次 HTTP 200 和两次 Embedding 429，按既有重试恢复；供应商配额限制不能抹掉。

[load.json](evidence/platform/load.json)：20MiB 合法双页 PDF 实际上传、审批、后台 ready；alpha 作业从受理到 ready 12.031s，beta 13.696s。120 个 0.5s 时间采样中，4 个同时观察 alpha parsing/indexing 与 beta queued；两个项目最终 ready。并发开始的旧库 Agent 查询 31.703s，后续查询 27.824s 均 success。这包含 Agent 执行耗时，不与裸 MCP 检索延迟混用。

[snapshots-30.json](evidence/snapshots-30.json) 是 30 文档确定性模型压力，不能冒充真实模型吞吐：恢复零新增调用、首快照不变、shared keys 最终 close 后 0；第30快照约1.05MB、全 root 约17.97MB。完整历史空间仍增长，不自动删历史。配额超额／锁回收／lease 的拒绝与恢复在自动回归覆盖。

[resources.json](evidence/resources.json)：Ubuntu 4 核，MemTotal 3,812,564KiB；RAG 服务最终 VmHWM/VmRSS 约326,340KiB，未采样 parser 子进程峰值。20MiB 样本是两页边界文件，不等价同大小高密度业务 PDF，也不是生产最大容量／吞吐或 SLA。真实用量保留，金额缺可核验完整费率为 null。

## Final 验证

本轮最终执行记录见 [final-checks.json](evidence/final-checks.json)。

- Ubuntu 全套 `uv run --frozen --env-file ".env" pytest tests/ -q`：**119 passed / 27.32s**，0 failed，0 skipped。
- 16 个本期 Python 文件 ruff format/check：通过；compileall src/tests/scripts：通过；git diff --check：通过；uv lock --check：通过；uv pip check：224 个包兼容。锁文件无变更。
- 平台 API 知识／授权／模型策略：42 passed + 269 subtests /29.89s；Runtime 知识／授权／Office：156 passed /94.23s。
- 平台 API Token／后台回执相关：113 passed、1 skipped /26.28s；Runtime Token／后台相关：196 passed、35 skipped /53.82s。跳过项需要显式隔离 PG／容器 opt-in 条件，不标为已执行。本期真实知识链路本身使用独立 PG／Redis／Worker。
- Web 知识＋Token／后台投影：14 个文件、93 passed /19.15s；typecheck 0 error。主工作区既有功能没有覆盖，本次 union 相关基线通过，不等同正式主线全量回归。
- .env、私有凭据和 parser 原始日志不入库；交付 JSON／patch／截图扫描 secrets、Bearer、私钥和宿主临时路径，已确认公开 sources 不含原路径；首次失败 JSON 保留，原始日志在 Ubuntu 忽略目录保留。

本次所属服务已停止（Ubuntu 28892／28893、union Web/API/Runtime/Redis 及浏览器），端口关闭和进程退出见 [service-stop.json](evidence/service-stop.json)。功能提交 `09ac6a9e945f0a1eb6a9e3ecdb2a8c35efafb5d3` 已推送到 `origin/feat/online-documents-20261013`，git ls-remote 与 HEAD 一致，功能提交后工作区干净；交付见 [delivery.json](delivery.json)。本记录由随后文档收尾提交携带，最终远端和工作区再次检查。

## 最终结论

**done（本期范围）**：实现与验收通过，所属服务已停，Ubuntu 工作分支已推送。平台正式合入／v2 展示／图片 ImageRef 收据／生产部署不记作完成；音视频用户暂不开发。私有业务和生产容量结论需对应语料与指标。
