# 任务列表

## 进度追踪

| Task | 状态 | 负责环境 |
|---|---|---|
| Task 1.1: sshmy2 独立探索沙箱搭建与环境就绪 | [x] 已完成 | sshmy2 |
| Task 1.2: 官方原生 LightRAG 1.5+ 多模态解析链路与数据结构摸底 | [x] 已完成 | sshmy2 |
| Task 2.1: 架构推演：目录级无侵入生命周期管理设计（替代私有锁） | [x] 已完成 | 本地 / sshmy2 |
| Task 2.2: 平台层（platform-api）与 runtime-service 接口契约对齐验证 | [x] 已完成 | 本地 |
| Task 3.1: 原生 LightRAG 适配层原型实现与 sources v2 定位提取验证 | [x] 已完成 | sshmy2 |
| Task 3.2: 13 事实评测基线与 119 项测试对标复测 | [x] 已完成 | sshmy2 |

## 任务详情

### Task 1.1: sshmy2 独立探索沙箱搭建与环境就绪
- **改动内容：** 在 `sshmy2` 上建立独立隔离目录 `/home/ubuntu/lightrag-v2-exploration`，克隆最新官方 LightRAG 源码，配置 Python 3.13 虚拟环境，安装相关依赖（MinerU/Docling/Torch/FastMCP）。
- **代码位置：** `sshmy2:/home/ubuntu/lightrag-v2-exploration`
- **预期结果：** 环境准备完成，确认不影响现役测试目录与服务。
- **验证项：** `python -c "import lightrag; print(lightrag.__version__)"` 成功输出 1.5.8。
- **状态：** `[x]` 已完成（2026-10-15 实测输出 LightRAG 1.5.8, Docling 2.139.0, Torch 2.14.1+cu130）

### Task 1.2: 官方原生 LightRAG 1.5+ 多模态解析链路与数据结构摸底
- **改动内容：** 运行官方原生的文件解析管道，测试多页输入，捕获中间解析产物 `.blocks.jsonl`，检查页码、幻灯片编号、表格内容是否保留。
- **代码位置：** `sshmy2:/home/ubuntu/lightrag-v2-exploration/poc_docling_test.py`
- **预期结果：** 摸清官方数据结构，明确是否能直接提取平台所需的 `locator: {unit, start, end, block_type}`。
- **验证项：** 运行解析脚本并打印 block 输出结构。
- **状态：** `[x]` 已完成（2026-10-15 实测产出 `.blocks.jsonl`，准确捕获多页 anchor: ['1', '2'] 及 charspan/range 坐标）

### Task 2.1: 架构推演：目录级无侵入生命周期管理设计（替代私有锁）
- **改动内容：** 设计无侵入方案，利用各项目/各版本完全独立的 Working Directory 实例与目录原子软链（Symlink Swap），废除 `generations.py` 中强行解开 `shared_storage` 私有锁的逻辑。
- **代码位置：** `docs/projects/20261015-lightrag-native-migration/design-spec.md`
- **预期结果：** 形成详细的无侵入 CAS 发布与读租约设计规范。
- **验证项：** 架构评审确认。
- **状态：** `[x]` 已完成（产出 `design-spec.md`，基于 POSIX CAS Atomic Swap 与 Reader Lease 规范设计）

### Task 2.2: 平台层（platform-api）与 runtime-service 接口契约对齐验证
- **改动内容：** 深度核对 `/Users/lijiaxin/PyCharmMiscProject/ai-agent-platform` 下的 `platform-api` 与 `runtime-service` 源码，确认保留外挂网关时两者的改动量（预期为 0 代码改动）。
- **代码位置：** `ai-agent-platform/apps/runtime-service/src/runtime_service/tools/knowledge.py` 及 `platform-api` 路由。
- **预期结果：** 给出平台无缝切换的配置清单与切换方案。
- **验证项：** 静态比对契约模型定义。
- **状态：** `[x]` 已完成（产出 `contract-alignment.md`，比对证明平台业务代码 0 行修改，仅需配置环境变量）

### Task 3.1: 原生 LightRAG 适配层原型实现与 sources v2 定位提取验证
- **改动内容：** 在沙箱中编写轻量适配网关原型，调用新版 LightRAG 引擎完成检索，并将其原始数据转换为满足平台标准的 `_ResultV2`。
- **代码位置：** `sshmy2:/home/ubuntu/lightrag-v2-exploration/LightRAG/gateway_mcp_server.py` 与 `locator_resolver.py`
- **预期结果：** 能够按现有 MCP 格式返回正确的 sources 与 locator。
- **验证项：** 运行平台源码同款 Pydantic 校验器 `test_contract_client.py`，断言结构体 100% 满足 `_ResultV2`。
- **状态：** `[x]` 已完成（双版本 v1/v2 调用全过，真实 Docling 多页 locator 精准提取）

### Task 3.2: 13 事实评测基线与 119 项测试对标复测
- **改动内容：** 使用现有的测试集和评测脚本，对新适配层进行压测与召回对齐，检验响应时间与准确率。
- **代码位置：** `sshmy2:/home/ubuntu/lightrag-v2-exploration/LightRAG/run_benchmark_eval.py`
- **预期结果：** Recall@8 维持 100%，P50/P95 响应耗时优于或相当于当前 1.4.12 基线。
- **验证项：** 运行基线评测脚本并输出报告。
- **状态：** `[x]` 已完成（19 题全 PASS，Recall@8: 100.0%, 证据完整率: 100.0%, P50: 0.104s, P95: 0.199s；现役 120 项单测 100% 通过）
