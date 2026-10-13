# 验证记录

## Phase 验证

### Task 1.1：供应商配置清理（2026-10-13）

- 本机 `.env` 无旧供应商引用，本机源码／脚本／tests／examples／`env.example`／锁文件扫描命中0；Ubuntu项目源码／脚本／examples无专用调用，项目 `.env`、`env.example` 旧视觉配置已删除，隔离目录同样无运行引用。
- 本机与Ubuntu用 `dotenv_values` 脱敏断言：VISION端点／模型／密钥分别等于LLM；视觉预算8192，不输出密钥。
- 本机 `uv run --frozen --env-file ".env" pytest "tests/test_llm_configuration.py" "tests/test_raganything_compatibility.py" -q` → **2 passed、6 skipped / 2.55s**。Intel Mac缺documents依赖，六项不伪记通过。
- Ubuntu隔离冻结环境中显式 `load_dotenv` 读取更新后的项目私有env，再执行同一集合 → **8 passed / 8.63s**。
- Ubuntu `build_vision_model_func` 原样调用合成JPEG，无 `extra_body` 覆盖 → 形状／颜色／数量均正确，见[图片证据](vision-check.json)。现有通用适配器足够，未修改产品Python代码。
- 首次探针加载env前，`uv --env-file` 解析旧格式scopes JSON警告回显过一个MCP token，随后的配置配对断言失败，尚未调用模型。规范化为转义单行JSON后映射值不变，改为进程内显式加载，真实请求通过。token值未写仓库；启服前应协调消费方轮换。

### Task 1.2：剩余事项说明（2026-10-13）

- RAG Task2.2／4.1原定后置，复杂文档partial和真实模型失败证据保留；新增[剩余事项](../../remaining-work.md)区分未开发与待验收。
- 只读核对平台最新任务：A01／A02／R01／R02／O01／V01与F01–F03代码已交付，V02完整Agent／浏览器及生命周期验收仍partial。说明不要求用户亲自在Ubuntu写代码，`sshmy2`可供开发代理做解析集成验证。
- 第一轮受影响Markdown本地链接 **45个检查通过**；README／进展／运行指南／CONTEXT／FEATURES及原专项任务同步，早期示例标记为历史并移除过期配置块。

## Final 验证

- [x] 本机完整冻结锁回归：`uv run --frozen --env-file ".env" pytest "tests" -q` → **101 passed、6 skipped / 39.98s**。Ubuntu八项模型／真实documents回归补齐本机跳过范围；本轮未重复Ubuntu全部107项。
- [x] 运行源码／示例／本机与Ubuntu项目env及示例旧供应商引用为零；15份改动／新增文档与配置对本机、Ubuntu项目实际私有密钥／token扫描均命中0，不输出凭据值。首次工具警告回显token的事实及轮换事项如上记录，不宣称本轮从未有凭据输出。
- [x] Ubuntu更新配置后的独立临时库使用真实DeepSeek／百炼模型，`scripts/verify_online_knowledge.py::run` → 六检查均true：queued、worker ready、重复零新增usage、新旧MCP来源、回退可查、published文件不变。签名授权为本地桩，不是平台Agent／浏览器验收。见[脱敏链路证据](chain-check.json)；完整结果保留Ubuntu隔离目录，现役数据未改。
- [x] `ruff check --select F,E9 src scripts tests`、`compileall`、`uv lock --check`、`git diff --check`均exit0；没有新增依赖或修改产品Python代码。
- [x] tasks两项完成与两条Phase对应，README状态done，CONTEXT／FEATURES及剩余事项保持后置范围；最终15份文件的JSON、状态断言及59个本地链接检查通过。Ubuntu现役项目／隔离目录未发现RAG服务或builder进程，全部多模态开关仍false、online未设（默认false）。

## 最终结论

**`done`：用户本次要求的供应商运行配置清理与剩余事项说明已完成并验证。** 不代表复杂PDF／Office全部支持、online多模态／公开页码／音视频已开发或V02／生产部署已验收；这些状态仍在[剩余事项](../../remaining-work.md)中跟踪。服务保持停止，未切换现役索引，未执行本轮Git提交／推送。
