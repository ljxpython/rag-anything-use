# 工业级生命周期管理与无侵入存储架构设计规范 (Design Spec)

> **设计目标：** 彻底废除旧版针对 LightRAG 1.4.12 `shared_storage` 私有全局锁与内部字典的 Monkey Patch 强解逻辑（`release_workspace`），基于 POSIX 原生原子文件系统能力实现租户与版本完全隔离的生命周期管理（CAS Atomic Swap & Reader Lease）。

---

## 1. 历史痛点与切斯特顿栅栏审视 (Why Old Logic Was Toxic)

在旧版实现 (`src/knowledge/generations.py`) 中，由于 LightRAG 1.4.12 将存储状态与锁集中在模块全局变量 `lightrag.kg.shared_storage`，导致代码不得不引入以下极其脆弱的侵入式逻辑：
```python
# 旧版的危险 Hack 代码：强行穿透私有变量
if version("lightrag-hku") != "1.4.12" or shared._is_multiprocess:
    raise ValueError("knowledge_storage_version_unsupported")
prefix = workspace + ":"
keyed = shared._storage_keyed_lock
if keyed:
    for mapping in (keyed._async_lock, keyed._async_lock_count, keyed._async_lock_cleanup_data):
        for key in list(mapping):
            if key.startswith(prefix):
                del mapping[key]  # 强行删除底层锁字典
```

### 痛点根因：
1. **强版本绑定与脆断：** 只要上游小版本升级（如 1.5.8），私有字典结构或锁逻辑微调就会直接导致 `ValueError` 阻断全流程。
2. **脏状态残留风险：** 手动 `del mapping[key]` 绕过了正常的锁生命周期与垃圾回收，极易导致并发状态下的竞态死锁或内存泄露。
3. **缺乏进程间物理隔离：** 多工作区运行在同一进程空间内，一旦底层代码发生未捕获异常，所有 workspace 互相踩踏。

---

## 2. 目录级无侵入架构设计 (Zero-Intrusion Directory Architecture)

### 2.1 物理存储拓扑

所有持久化资产按**租户 (Tenant)** 与 **项目 (Project)** 严格划分物理目录，彻底隔离文件系统：

```text
storage/
├── <tenant_id>/
│   └── <project_id>/
│       ├── active -> revisions/rev_2/         # POSIX 原子软链：始终指向当前生效版本
│       ├── revisions/                         # 只读不可变版本归档
│       │   ├── rev_1/
│       │   │   ├── kv_store_*.json
│       │   │   ├── graph_chunk_entity_relation.graphml
│       │   │   ├── vdb_chunks.json
│       │   │   └── manifest.json              # 冻结签名与资产校验摘要
│       │   └── rev_2/
│       │       └── ...
│       ├── candidates/                        # 增量/构建中沙箱（对外不可见）
│       │   └── cand_9a3c8e71/
│       │       └── ...
│       └── uploads/                           # 原始受管附件与中间解析产物
│           └── <doc_id>/
│               ├── source.pdf
│               └── .blocks.jsonl              # 多模态解析坐标缓存
```

---

## 3. 核心机制设计

### 3.1 零锁增量构建 (Lock-Free Incremental Ingest)
1. **候选沙箱分配：** 当接收到入库任务时，在 `candidates/cand_<uuid>` 创建独立临时目录。
2. **基线快速继承：** 
   - 若当前项目存在 `active` 版本，通过硬链接（`cp -al`）或文件复制将已冻结的存储文件同步至候选目录；
   - 保证基线数据的读取不阻塞生产流量。
3. **原生引擎写入：** 独立实例化 `LightRAG(working_dir=cand_path)`，直接调用官方原生的 `ainsert` 或 `ainsert_custom_chunks`。
4. **资产密封与校验 (Seal & Manifest)：** 构建完成计算所有物理存储文件的 SHA256，生成 `manifest.json`，验证无损后将候选目录重命名移动至 `revisions/rev_<next>`。

### 3.2 POSIX 原子软链切换 (Atomic Symlink Swap)
放弃任何应用层的分布式锁或进程内互斥锁，直接利用 Linux 内核级别的原子软链重命名机制完成发布：

```bash
# 1. 创建指向新版本的临时符号链接
ln -sfn revisions/rev_<next> active.tmp

# 2. Linux POSIX 原子的符号链接覆盖切换 (Atomic Swap)
# 在任何并发读请求视角下，active 永远是指向旧版本或新版本，绝无中间态
mv -T active.tmp active
```

### 3.3 读租约与优雅平滑下线 (Reader Lease & Graceful Drain)
为防止新版本激活瞬间正在执行查询的请求出现文件句柄突变：
1. **Lease 计数器：** 每个查询在进入时持有当前已加载 LightRAG 实例的读租约（`lease_count += 1`），查询结束后释放（`lease_count -= 1`）。
2. **延迟退休：** 当后台检测到 `active` 软链目标改变时，将旧实例标记为 `Draining`，停止接收新查询。
3. **平滑释放：** 轮询直至旧实例的 `lease_count == 0`，调用其底层的干净清理逻辑或等待 GC 回收，完全不需要暴力操作内部私有字典。

---

## 4. 平台契约零侵入映射表 (Platform Contract Mapping)

| 平台规范 (`runtime-service` / `platform-api`) | 网关层适配逻辑 (Gateway) | LightRAG 1.5+ 原生对应 |
|---|---|---|
| `mcp_query_project_knowledge` | 提取 `tenant_id` 与 `project_id` 路由到对应 `active` 目录 | `LightRAG.aquery_data(query, param)` |
| `sources_version=1` | 输出 7 个基础字段，`title` 严格遵循 `^\[\d{1,2}\] [^/\\\r\n]{1,160}$` | 映射 chunk 内容与关联文件名 |
| `sources_version=2` | 增补 `locator: {unit, start, end, block_type}` | 从 `.blocks.jsonl` 中匹配 `charspan` / `page_idx` |
| `kd_[a-f0-9]{32}` | 保留平台统一的 `document_id` 命名规范 | chunk metadata 中的 doc_id 字段 |
| 宿主机路径隐藏 | 绝不将服务器绝对路径暴露在 preview 或 title 中 | 只暴露 `Path(file_path).name` |

---

## 5. 架构收益总结
- **100% 官方原生兼容：** 核心引擎只依赖官方公布的公共 API（`ainsert`, `aquery_data`, `initialize_storages`），杜绝任何 monkey patch。
- **天然高并发与进程安全：** 存储隔离在物理目录层，读写完全物理隔离，崩溃不蔓延。
- **免锁极简：** 消除 300+ 行脆弱的私有锁破解代码，代码量降低 70%，遵循老王 Karpathy / KISS 准则。
