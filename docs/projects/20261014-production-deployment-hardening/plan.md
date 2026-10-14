# RAG 生产部署加固方案 - 整体方案

## 背景
`rag-anything-use` 之前在开发联调期间主要通过临时命令行启动，并依赖 SSH 隧道反向映射打洞。进入生产部署阶段后，需要脱离对客户端 SSH 会话和临时端口的依赖，支持公网/VPC 域名直接提供服务。目前系统在运维与高负载防护上存在三个核心缺口：
1. 缺少可靠的常驻后台守护，进程崩溃或服务器重启后无法自愈；
2. 缺少安全反向代理，FastMCP 服务裸跑 HTTP，且大文件上传可能被默认中间件截断；
3. 文档解析（Docling/OCR/LightRAG）属于高负载计算密集型任务，当单台机器多核被打满时，主服务的事件循环可能失去调度时间片，导致 HTTP 探活与 MCP 请求超时。

## 目标
1. 补齐生产级 Systemd 常驻服务配置与日志轮转；
2. 补齐生产级 Nginx 反向代理配置（支持 HTTPS、大文件上传、SSE 流式长连接）；
3. 补齐计算密集型任务（Builder 子进程）的 CPU 与线程资源隔离，确保高负载下主 MCP Server 响应依然流畅（探活延迟 < 200ms）；
4. 提供清晰的 Ubuntu 服务器环境准备清单与操作手册。

## 方案设计

### 1. 常驻守护方案 (Systemd Service)
- **文件位置：** `deploy/rag-service.service`
- **设计细节：**
  - 使用 `Type=simple`，指定工作目录为 `/opt/rag-anything-use`（或对应部署路径）。
  - 使用专用运行账号（如 `raguser` 或现有的 `ubuntu`），避免直接使用 root 运行。
  - 配置 `EnvironmentFile=/etc/rag-service/rag.env` 集中管理生产配置。
  - 配置 `Restart=always`，`RestartSec=5s` 实现异常崩溃秒级自愈。
  - 标准输出与错误重定向至 systemd journal（支持 `journalctl -u rag-service -f` 统一查看）。
  - 设置 `KillMode=mixed` 与 `TimeoutStopSec=30`，允许服务在收到 SIGTERM 时优雅执行 `supervisor.stop()` 并回收子进程。

### 2. 反向代理方案 (Nginx TLS / Streamable HTTP)
- **文件位置：** `deploy/nginx-rag.conf`
- **设计细节：**
  - **SSL/TLS 终止**：监听 443（HTTPS），配置生产证书路径，禁止不安全的 TLSv1.0/1.1。
  - **大文件上传放通**：配置 `client_max_body_size 50M;`，防止用户上传大型 DOCX/PDF 报 413 Request Entity Too Large。
  - **流式长连接防护**：
    - `proxy_buffering off;`（关键！防止 Nginx 缓冲 FastMCP 的 SSE 流式响应，导致流式内容卡死直到缓冲区满才输出）；
    - `proxy_read_timeout 600s;` 与 `proxy_send_timeout 600s;`（放宽超时时间，防止大型文档上传或复杂检索被 504 截断）；
    - `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` 透传真实客户端 IP。

### 3. 计算密集型任务防阻塞方案
- **现状分析：**
  在 `src/knowledge/job_worker.py` 中，`KnowledgeJobSupervisor` 已经通过 `asyncio.create_subprocess_exec` 拉起了独立的 Python 子进程执行任务构建，这已经避免了 Python GIL 在同一进程内阻塞事件循环。
- **现存痛点：**
  当子进程加载 PyTorch / ONNX / Docling 进行复杂文档 OCR 和图构建时，底层 C++ 库（如 OpenMP、MKL、BLAS）默认会抢占**机器上的所有 CPU 核心**，导致宿主机负载飙升至 100%，操作系统内核无法给主 Python 进程分配时间片，从而引起主服务卡死。
- **解决方案（多重资源降级与限流）：**
  1. **环境变量限制子进程线程**：
     在 `job_worker.py` 启动子进程的 `env` 中显式注入线程限制：
     ```python
     "OMP_NUM_THREADS": "2",
     "MKL_NUM_THREADS": "2",
     "OPENBLAS_NUM_THREADS": "2",
     "VECLIB_MAXIMUM_THREADS": "2",
     "NUMEXPR_NUM_THREADS": "2",
     ```
  2. **降低子进程调度优先级（nice）**：
     在启动子进程时，通过 `preexec_fn`（或 `nice` 命令）将子进程的优先级调整为较低值（如 `os.nice(10)`），确保操作系统的调度器永远优先保障主 MCP Server 的网络事件循环处理。
  3. **并发排队控制**：
     严格保持 `.builder.lock` 单并发处理机制，后续任务排队，杜绝多个高内存/高 CPU 文档任务并发导致 OOM。

## 链路影响与契约一致性
- 对外接口（MCP Tools、HTTP 端点）完全不变，无需升级协议。
- 平台端（`runtime-service` / `platform-api`）只需将原有的 `127.0.0.1:{local_port}` 改为该 Nginx 对外暴露的 `https://<rag-domain>`，全链路无缝贯通。
