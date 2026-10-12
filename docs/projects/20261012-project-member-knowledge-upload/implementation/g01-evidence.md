# G01 完整快照恢复与原生增量证据

2026-10-12。本机 Intel macOS / Python 3.13，锁定 LightRAG 1.4.12、FastMCP 3.2.0；真实模型沿现有 `.env`：DeepSeek `deepseek-v4.1-flash`、百炼 OpenAI 兼容 `text-embedding-v4` / 1024 维。全部原件为脚本内生成的非敏感 A/B/C/D，使用独立临时目录，不读写用户已发布库。

可重复执行（不包含 RTK 包装）：

```sh
uv run --frozen --env-file ".env" python scripts/verify_incremental_snapshot.py --output docs/projects/20261012-project-member-knowledge-upload/implementation/g01-mock.json
uv run --frozen --env-file ".env" python scripts/verify_incremental_snapshot.py --real --output docs/projects/20261012-project-member-knowledge-upload/implementation/g01-real.json
```

原始脱敏结果：[mock](g01-mock.json)、[真实模型](g01-real.json)。请求计数在 `httpx.AsyncClient.send`，包括 SDK/模型重试；只保存输入摘要，不打印模型输入或密钥。查询请求单列，不纳入重复提交零入库请求断言。

| 阶段 | mock LLM / Embedding | 真实 HTTP LLM / Embedding | 已有相同输入重发 |
|---|---|---|---|
| A/B baseline | 4 / 8 | 6 / 27 | 首次建立 |
| 完整快照恢复 | 0 / 0 | 0 / 0 | 0 |
| 重复 A（相同稳定 ID） | 0 / 0 | 0 / 0 | 0 |
| 仅新增 C | 2 / 4 | 3 / 10 | 0 |
| 重启后仅新增 D | 2 / 4 | 3 / 10 | 0 |

真实模型发生一次 SDK 重试及空正文重试；空正文响应仍有 provider usage，不能视为免费失败。供应商响应的 `cost/gateway_cost` 无可确认币种/费率，不合计金额。记录原 usage，金额为 null。

12 项存储由显式 `index_done_callback()` 全部落盘，再 `finalize_storages()`。完整集合包括 full_docs、text_chunks、full_entities、full_relations、entity_chunks、relation_chunks、llm_response_cache、doc_status、三项 NanoVector 存储和 GraphML。`finalize_storages()` 会吞下部分 finalize 错误，因此后续实现必须显式 flush、检查持久内容和 checksum，不能只看 finalize 返回。

各实现的文件名只包含 storage namespace；workspace 是目录和进程内 shared_storage 键。候选恢复时把这 12 项文件复制到**新候选 workspace 子目录**，在构造 LightRAG 前完成恢复（NetworkX/NanoVector 构造即加载）；保持文件内 document/chunk/entity/relation IDs，不复用旧 workspace 名。baseline 全文件 SHA-256 在 C/D 处理与故障后不变。内存/进程内共享状态依赖 workspace，新候选隔离，发布后的磁盘快照必须冻结；请求缓存应驻留可抛弃的读副本，不能写已发布快照。

失败注入：候选 chunks Embedding 抛错，候选 C 不为 processed；baseline 校验和不变；从 baseline 重建独立回退实例，A/B 仍可检索，C 不存在。A/B/C 与重启后 A/B/C/D 均通过完整文档、processed 状态及 naive 检索来源断言。此证据验证底层存储恢复，尚不代替平台权限、HTTP/MCP 回执、原子 active 指针、在途查询 lease 和 supervisor 进程故障验收；这些由 K01–K08 补齐。

选型：只实现“已发布完整冻结快照 → 新 workspace 候选 → 新文档原生增量 → 全存储 flush/校验 → 原子激活”。不选全量 ainsert 重组，不选 base＋delta；不移除 published 不可变规则。签名/文件缺失、未知版本、checksum 错误一律拒绝恢复；不自动退回无缓存全量重建。费用随新增文档及受影响图数据变化，小语料不能替代代表性规模/ Linux 格式验收。
