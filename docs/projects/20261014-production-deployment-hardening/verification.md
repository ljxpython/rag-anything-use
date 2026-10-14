# RAG 生产部署加固方案 - 验证记录

## 验证计划

### 1. 本地代码与单测验证
- 执行单元测试套件：`uv run --frozen --env-file ".env" pytest tests/ -q`
- 确保新增线程限制与优先级调整不破坏子进程拉起与退出状态检测。

### 2. 高负载防阻塞验证
- 模拟大文件并发提交，同时通过外部高频 curl 请求 `/internal/knowledge/capabilities` 和 `/mcp`。
- 验收指标：子进程运行期间，HTTP GET 请求响应时间稳定在 200ms 以内，无假死无丢包。

### 3. Systemd 运维自愈验证
- 启动服务：`sudo systemctl start rag-service`
- 异常退出测试：`kill -9 <main_pid>`，观察 5 秒内 systemd 是否自动拉起新进程并成功恢复 supervisor 锁。
- 优雅关闭测试：`sudo systemctl stop rag-service`，验证正在处理的任务是否妥善取消，无残留孤儿进程。

### 4. Nginx 反向代理与流式长连接验证
- 校验大文件上传：使用 20MB 测试文件上传，验证无 413 错误。
- 校验流式返回：验证 FastMCP 工具返回的 SSE 数据能够实时刷出，不被 proxy buffer 截留。

## 验证执行记录

| 验证项 | 测试命令/步骤 | 预期结果 | 实际结果 | 判定 |
| :--- | :--- | :--- | :--- | :--- |
| 代码回归 | `uv run pytest tests/ -q` | 101 passed, 6 skipped | 101 passed, 6 skipped in 37.74s，无任何报错 | ✅ 通过 |
| 远端运行 | `systemctl status rag-service` | active (running)，监听 8000 | 成功启动并稳定监听 `0.0.0.0:8000` | ✅ 通过 |
| 崩溃自愈 | `sudo pkill -9 -f src/mcp_server.py` | 5s 内自动重启恢复 | 触发 auto-restart，5s 内成功由 systemd 拉起新 PID 恢复服务 | ✅ 通过 |
| 外部直连探活 | `curl http://152.136.27.196:8000/internal/knowledge/capabilities` | 返回 200 HTTP Capabilities | 成功返回 200 OK，能力 JSON 响应正常 (耗时数十毫秒) | ✅ 通过 |
| MCP 协议探测 | `curl -X POST http://152.136.27.196:8000/mcp` | 成功建立 Streamable HTTP 协议握手 | 返回 mcp-session-id，Streamable HTTP 握手响应正常 | ✅ 通过 |

