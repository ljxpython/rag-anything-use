# RAG 生产部署加固方案 (Production Deployment Hardening)

## 项目概述
- **时间：** 2026-10-14 至 2026-10-15
- **目标：** 为 `rag-anything-use` 知识库服务补齐生产级常驻守护（Systemd）、反向代理（Nginx TLS/SSE）与计算密集型任务防阻塞隔离，支持生产环境直接 URL 暴露与稳定长效运行。
- **负责人：** 老王
- **模板类型：** 标准模板
- **状态：** 规划中（待实施与验证）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响模块：** `deploy/`（新增 systemd 配置与 nginx 模板）、`src/knowledge/job_worker.py`（计算密集型子进程参数与资源防护）、`env.example`（生产环境配置范例）、文档与运行手册。
- **改动级别：** 架构/治理改动
- **预计工作量：** 1 人天

## 关键决策
1. **常驻守护选型**：使用 Linux 原生 `systemd` 服务托管，避免使用复杂的容器套娃，实现开机自启、故障自愈、标准日志与平滑优雅关机（SIGTERM）。
2. **反向代理与 TLS**：前置 Nginx 处理 SSL/TLS 证书终止，配置 `client_max_body_size 50M`，关闭代理缓冲（`proxy_buffering off`）以原生支持 FastMCP 的长连接与 SSE 流式返回。
3. **计算密集型任务防阻塞**：在已有的子进程隔离架构基础上，通过限制底层数学库线程数（`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`）、降低子进程调度优先级（`nice`）以及配合 Systemd CPU/内存 配额，防止 Docling/PyTorch 占用 100% CPU 导致主 MCP HTTP 事件循环假死。
4. **存储与路径决策**：遵循用户指示，数据存储路径本期保持现状，不增加复杂迁移逻辑。
