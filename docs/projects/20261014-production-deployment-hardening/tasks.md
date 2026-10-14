# RAG 生产部署加固方案 - 任务拆分

## 任务清单

- [x] **Task 1: 计算密集型任务子进程防阻塞改造**
  - [x] 1.1 在 `src/knowledge/job_worker.py` 的子进程环境变量中注入底层数学库线程限制 (`OMP_NUM_THREADS`, `MKL_NUM_THREADS` 等)。
  - [x] 1.2 在子进程创建时配置进程低优先级 (`nice` 值)，避免抢占主服务调度时间片。
  - [x] 1.3 运行已有测试，确保改造后不破坏任务中断、超时和正常发布流程 (101 passed, 6 skipped)。

- [x] **Task 2: 编写生产部署模板与配置**
  - [x] 2.1 创建 `deploy/rag-service.service` 生产 Systemd 单元文件模板。
  - [x] 2.2 创建 `deploy/nginx-rag.conf` 生产 Nginx 反向代理配置模板（含长连接、大文件、SSE 缓冲优化）。
  - [x] 2.3 更新 `env.example`，补充生产环境必须配置项说明（`KNOWLEDGE_AUTHORIZE_URL`、`KNOWLEDGE_ONLINE_ENABLED`、`MCP_HOST` 等）。

- [x] **Task 3: Ubuntu 生产服务器部署与连通性验证**
  - [x] 3.1 梳理 Ubuntu 权限开通清单（安全组端口、UFW、用户目录权限、证书）。
  - [x] 3.2 部署文件至 Ubuntu 机器并启动 Systemd 服务 (`rag-service.service` 成功激活运行)。
  - [x] 3.3 验证外部公网直连 (从本地发起 curl 成功返回 200 HTTP Capabilities 及 Streamable MCP 响应) 与崩溃秒级自愈 (kill -9 自动恢复)。

- [ ] **Task 4: AI Agent 平台直连适配与收工验证**
  - [ ] 4.1 在 `platform-api` 与 `runtime-service` 的 `.env` 中填入生产直接 URL。
  - [ ] 4.2 重启平台服务，脱离 `connect_ubuntu_rag.py` 脚本完成真实连通性测试。
