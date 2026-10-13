# 项目当前状态

## 最后更新

2026-10-13 | Ubuntu 分支 feat/online-documents-20261013 完成在线 PDF／DOCX／PPTX／PNG／JPEG、受管资产与来源 v2；五格式13事实全过、真实平台 union 文档闭环及生命周期通过；RAG119 passed、19题公开基线有答案召回／证据1.0、P50/P95 2.948/3.564秒、20MiB／两项目队列已验。平台正式合入／v2展示／ImageRef收据待协同，音视频延期；现役索引未切换

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `src/mcp_server.py` | 原只读／精确提交工具保留；query 显式 sources_version=1或2 | 默认v1来源七字段不变；v2可信locator，不返回宿主路径；失ACK GET按原主体／当前grant回查 |
| `src/cli.py` | 稳定；注册/迁移/回退3命令；main入口已正确传播失败退出码 | 管理员专用；迁移需冻结旧服务与确认全部处理签名 |
| `src/knowledge/` | 文档容器校验、完整成果与受管资产、严格多模态失败、文档／图片原生增量及可信定位 | 完整候选／CAS／reader lease／回退；旧快照零新增模型；损坏拒绝；旧文本签名精确兼容；POSIX单服务进程 |
| 测试套件 | ✅ Ubuntu119项通过（27.32s），16文件ruff／compileall／frozen依赖通过 | 原授权／失ACK／增量／迁移／回退保留；API知识42+269子测试、Runtime知识156、Web知识及Token后台93通过，平台可选PG／容器跳过单列 |

## 环境说明

- Python ≥ 3.13，uv
- RAG-Anything 1.4.2 / MinerU 3.4.5 / Docling 2.84.0；LightRAG 1.4.12 / FastMCP 3.2.0保留（锁定版本）
- 2026-10-12本轮真实验证：miaomiaoai `deepseek-v4.1-flash` + 百炼 OpenAI兼容 `text-embedding-v4` 1024维；2026-10-11旧只读专项曾使用Ollama768维，两套索引不可混用
- 2026-10-13本机／Ubuntu项目VISION三项已显式复用LLM，视觉预算8192；`env.example`删除旧供应商及备用配置，运行源码无专用供应商调用。视觉配置也参与online处理签名，部署时不绕过旧库校验
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

- [Ubuntu 在线文档与联合验收](projects/20261013-online-documents/README.md)：本期 done，功能提交09ac6a9已推送同名远端分支、所属联验服务已停；临时 union 已真实验证文档链，平台主工作区未合并。PNG／JPEG 为真实模型＋受控授权验证，ImageRef 浏览器可信链后续协同。
- [模型供应商清理](projects/20261013-model-provider-cleanup/README.md) 与 [RAG升级](projects/20261012-rag-optimization/README.md)：原期 done，本次补齐旧后置文档／资产／定位／联合验收；历史失败证据保留。
- [成员异步入库](projects/20261012-project-member-knowledge-upload/README.md)：RAG与临时平台 V02 文档联验通过，正式平台合并／部署不标已完成；[授权与失ACK](projects/20261012-rag-provider-contract-alignment/README.md)保留。
- [剩余事项](remaining-work.md)：平台v2展示、图片收据／正式合入、私有业务与生产SLA；音视频用户暂不开发。旧token启服前协调消费方轮换，证据不含凭据。

## 近期关键决策

- 2026-10-13：按用户要求清理iflow／豆包运行配置；本机与Ubuntu私有VISION改用miaomiaoai `deepseek-v4.1-flash`，更新配置后既有适配器图片检查通过。图片小样不等于完整文档多模态验收；后置任务不以Ubuntu或旧视觉凭据作统一阻塞理由。
- 2026-10-12：在线文本新签名排除未使用的解析包版本；精确兼容已核验v1文本组合，保留旧签名/checksum。离线与在线新增chunk均以document ID隔离；多模态显式绑定本workspace，资产路径在batch/fallback索引模板中隐藏。
- 2026-10-12：后台identity持久保留graph_id及sha256/size/name/MIME；每次新issuer/audience/整数iat/exp/uuid nonce。新增同key GET不enqueue/不消费attempt，要求当前upload grant；RAG新写关闭不拒回查，平台停签会阻止获取新租约。旧缺字段任务不猜来源。
- 2026-10-12：实测固定完整快照候选＋新文档原生增量；不全库重组，不base＋delta。原生LLM缓存随快照恢复，不另加Embedding缓存；图更新必要费用单列，未知费率金额null。平台只接入，不持有第二套解析/索引队列。
- 2026-10-13：online默认false；依赖及完整多模态开关齐全才报告PDF／DOCX／PPTX／PNG／JPEG，其余只报告MD/TXT。迁移冻结legacy服务、保留旧ID/原件并确认处理签名；回退先禁上传、恢复完整累计版本后才重启上传。新chunk ID含document ID与workspace全局KV/锁回收绑定LightRAG1.4.12，升级需重验。
- 2026-10-13：当前 miaomiaoai 抽取实测 reasoning_effort:off；none 在复杂文档节点出现400，最终 off 五格式13事实全过。模型配置与多模态成果签名变动采用独立新库，不绕过旧签名。
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
