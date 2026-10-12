# 实施证据与复跑入口

2026-10-12实施证据；2026-10-13用户验收本期范围通过，需求关闭。Ubuntu证据来自sshmy2独立目录 `/home/ubuntu/rag-opt-20261012-65sx7w4w`。资料均为本项目创建的公开合成样本；真实模型测试产生调用费用。判定与未验证范围见[验收记录](../verification.md)。

| 证据 | 内容与边界 |
|---|---|
| [Ubuntu完整回归](final-tests-ubuntu.log) | 96 passed / 24.92s；已安装documents，模型调用由测试替换 |
| [Intel Mac完整回归](final-tests-macos.log) | 90 passed、6 skipped / 27.79s；documents未安装 |
| [检索基线](evaluation-baseline.json) | 3份资料、19题，真实CLI发布/HTTP MCP；16题Recall@8/证据完整率1.0，3题无答案仍返回资料 |
| [100文档快照观测](capacity-100-ubuntu.json) | 确定性模型和模拟DB激活；空间/复制/校验/reader观测，不是生产容量或IAM验收 |
| [真实在线文本链路](real-online.json) | 真实worker/HTTP MCP、重复零新增usage、回退与旧checksum；授权使用本地签名桩，非生产IAM |
| [初轮格式](formats-initial.json) | PDF/OCR、DOCX/PPTX正文通过；混合PDF表格事实被预览截断；旧done仅覆盖当轮已问的正文题 |
| [终轮格式原始报告](formats-final.json) | 文本/OCR通过；混合PDF/DOCX超时；旧main错误返回exit0使验证器在PPTX后中断，只保存4个格式 |
| [PPTX失败回执](release-ingest-failure.json) | 终轮实际accepted=false；空正文抽取失败，不能由旧exit0判成成功 |
| [视觉初探针](vision-probe.json) / [凭据探针](vision-auth-probe.json) | HTTP200、choices=0；后者明确业务码434及Invalid apiKey，图片分析blocked |
| [DeepSeek图片HTTP探针](deepseek-vision-probe.json) / [项目适配器](deepseek-adapter.json) | 2026-10-13miaomiaoai `deepseek-v4.1-flash`识别两张合成图片正确，既有vision适配器JPEG路径亦通过；只改过程级配置，未复跑完整文档多模态 |

首解析缓存、表格表示、来源/workspace/资产路径与CLI失败退出码已补回归。修正后的格式验证器未再次全量调用真实模型；原始报告保留实际失败，没有改成通过。Office/混合PDF的稳定性、表格/公式/图片完整文档链仍partial；两次600秒超时尚不足以定位全部根因。DeepSeek探针证明当前供应商模型ID的图片接口可用，不推断网关背后的模型实现；供应商usage中的cost原样保存，不作为已核验币种或账单。

复跑时使用自己的私有配置和独立目录。Ubuntu格式测试需先安装documents；Intel Mac仅支持本轮基础环境。

```bash
uv sync --frozen --extra documents --group dev
uv pip check
uv run --frozen --env-file ".env" pytest "tests" -q
uv run --frozen --env-file ".env" python "scripts/evaluate_knowledge.py" --output "/tmp/rag-evaluation.json"
uv run --frozen --env-file ".env" python "scripts/verify_document_formats.py" --output "/tmp/rag-formats.json"
uv run --frozen python "scripts/benchmark_knowledge_snapshots.py" --documents 100 --output "/tmp/rag-capacity.json"
```

三个脚本创建独立临时知识库，不改现役索引；前两个调用配置的模型。完整供应商日志保留在隔离环境，凭据不纳入本目录；未知费率金额为null。online多模态、公开页码、音视频、20 MiB文件与生产多项目负载后置；服务已停，新版未部署或迁移现役数据。
