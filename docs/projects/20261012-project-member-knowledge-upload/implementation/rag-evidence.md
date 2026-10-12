# RAG 实施验收证据

2026-10-12；隔离临时项目、合成非敏感文本、Intel macOS/Python3.13。锁定 LightRAG1.4.12、FastMCP3.2.0、httpx0.28.1、Starlette0.52.1；后两项仅声明既有锁定包为直接依赖，所有包版本保持不变。基线HEAD `790da30df5feabee6b988dd660adb0ac1acddf81`，未commit/push/部署。

## 路线与调用计数

[G01](g01-evidence.md)先验证完整12存储的冻结/恢复：恢复及重复A均零外部模型调用；真实baseline A/B为LLM6、Embedding27，C/D各3/10，旧相同输入重发0。候选Embedding故障不改变基线checksum，回退A/B仍查得到。后续实现固定完整快照候选＋新文档原生增量，不全库再次ainsert，不实现base＋delta。

真实实现链路执行：

```sh
uv run --frozen --env-file ".env" python "scripts/verify_online_knowledge.py" --output "docs/projects/20261012-project-member-knowledge-upload/implementation/rag-real-chain.json"
```

结果：[rag-real-chain.json](rag-real-chain.json)，6项检查全部true：HTTP接收→MCP持久queued→真实构建子进程→短授权→ready→真实MCP旧/新来源；重复原件无新增usage；回退searchable准确；旧12存储checksum不变。模型是现有 `.env` DeepSeek `deepseek-v4.1-flash`＋百炼 `text-embedding-v4` /1024维；平台为明确标注的本地签名授权桩，不能替代生产IAM或Agent两主图验收。

| 新文档 | 解析 | 图抽取HTTP | 新chunk Embedding | 新图 Embedding | 已有图更新 Embedding |
|---|---|---|---|---|---|
| A | 1 | 2 | 1 | 11 | 0 |
| B | 1 | 2 | 1 | 8 | 1 |
| 重复A | 0 | 0 | 0 | 0 | 0 |

模型输出会影响新实体/关系数量，故各次真实试验的请求总数可能不同。图合并LLM本次0；已有图更新的Embedding单列，不把必要合并费用误写成重做全部旧资料。LLM cache hit/miss是**lookup次数**，本次每job miss4，并不等于HTTP请求数。provider usage原样脱敏保留；没可核实币种/费率，金额null，不估计账单。查询模型费用未记入job零新增断言。

修复记录：先前真实链路触发上游关闭HTTP client后重试复用失败，随后暴露InvalidResponseError导入位置错误；[失败记录](rag-chain-failure.json)是后一次失败，已脱敏。现每次tenacity attempt建独立client、禁SDK隐式重试并计每次HTTP；测试复现两次调用/两个client。另修复共享Embedding队列继承首次ContextVar导致全部费用错归new_chunks的问题，改为入队前按输入摘要与旧vector ID登记阶段；真实链路已重跑。混合/未识别输入显式mixed_embedding/unknown_embedding，不强行猜阶段。

## Phase检查

| 范围 | 实际执行 | 结果 |
|---|---|---|
| K01 | `pytest tests/test_knowledge_jobs.py -q`，包括8线程同hash竞争、同key/failed/attempt上限、跨项目、ready/null、回退 | 与Final套件一起通过 |
| K02/K07 | `pytest tests/test_knowledge_upload.py tests/test_knowledge_migration.py -q` | 18 passed in3.29s；断流、乱码、hash/path/MIME/票据/配额、同字节不同扩展名只一原件；完整零模型迁移、缺原件/在线旧服务读锁拒绝 |
| K03 | `tests/test_knowledge_online_http.py`、原HTTP/stdio/security套件 | Final通过；六字段严格校验、无grant拒写、JSON文本同值、4KiB、安全GET、来源字段保持 |
| K04/K06/K08 | `pytest tests/test_knowledge_generations.py tests/test_knowledge_worker.py tests/test_knowledge_artifacts.py tests/test_llm_configuration.py -q` | 14 passed in7.00s（当时测试集合）；快照增量、撤权/base改变/损坏、旧lease/回退、成果checksum、实际输入计数与LLM重试 |
| K05 | `pytest tests/test_knowledge_worker.py -q` | 6 passed in9.03s；实际进程组timeout/cancel/SIGKILL、双supervisor、残留锁等待、真实父SIGKILL/子stdin watchdog/重启恢复 |
| 连续发布 | 最终 `test_continuous_generations_release_global_data_and_source_ids` | 10次mock发布，每次只1当前reader；旧workspace KV/async锁已回收，累计来源不丢 |
| 候选复制与取消 | `pytest tests/test_knowledge_generations.py -q` | 6 passed in9.28s；暂停复制仍可取得旧reader，取消后等后台IO结束才清目录 |

上表聚合命令均在本轮执行。未独立重复运行的单文件项明确随Final验证，不伪造每Task独立次数。20MiB校验逻辑按缩小边界单测，尚无代表性20MiB文档压力/P50/P95或Linux实机结果。

## Final

```sh
uv run --frozen --env-file ".env" pytest "tests" -q
uvx ruff check "src" "tests" "scripts" --select F,E9
git diff --check
```

结果：**67 passed in35.76s**；ruff F/E9通过；diff空白通过。真实链路由上方独立命令验证，不用单测代替。RAG文本范围done；整专项partial，待平台权限/附件/Runtime、前端、Linux格式、部署回退及代表性负载联合验收。

一次Final前回归为1 failed/66 passed in41.15s：SIGKILL fixture的15秒冷启动等待未到ready marker，SQL仅parsing且builder日志为空。补启动阶段/父日志诊断和所属子PID安全回收、将测试冷启动窗口设30秒后，worker套件6 passed in18.07s，Final67项通过；业务处理deadline不变。失败轮未当作通过证据，部署Linux仍需独立复验。

发布快照不可变、故障候选不active、原件持久先于queued、激活事务和当前授权、安全公开DTO已覆盖。外部请求已发送但结果未落盘不能承诺exactly-once计费；保留原件与失败记录，新明确提交有限重试。默认在线开关关闭，详见 [交接](rag-handoff.md)。
