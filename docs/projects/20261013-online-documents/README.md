# Ubuntu 在线文档与多模态开发、联合验收

- **时间：** 2026-10-13
- **目标：** 在 sshmy2 上补齐在线 PDF／Office／图片资产链，修复复杂格式稳定性，提供平台来源字段／展示协同方案，并验收真实平台闭环、通用业务检索和负载。
- **开发目录：** `/home/ubuntu/PyCharmMiscProject/rag-anything-use`
- **分支：** `feat/online-documents-20261013`，基于 `main@edd7963`。
- **平台源码：** `/Users/lijiaxin/PyCharmMiscProject/ai-agent-platform`；知识专项尚在同仓 6394 worktree 的未提交改动中，必须保护既有 Token／后台任务等主线功能。
- **状态：** 已完成（本期范围）；功能提交 `09ac6a9` 已推送，所属联验服务已停。
- **范围排除：** 用户明确暂不开发音频／视频；不删除历史索引，不直接更改现役已发布库，不部署生产。

## 实施约束

沿用原 FileRef、原件流式上传、任务、精确授权、持久幂等、完整冻结快照候选和原子激活。格式能力必须与真实解析／索引证据一致；解析资产保存到项目受管目录并校验，旧完整快照恢复不得重新解析旧原件或增加模型调用。缺损资产、路径逃逸、错误 MIME／容器或不兼容签名拒绝，失败候选不污染旧库。

真实模型继续使用 miaomiaoai `deepseek-v4.1-flash` 和百炼 `text-embedding-v4`／1024维；模型密钥仅从私有 env 加载。业务验收按用户2026-10-13回复使用通用公开资料，不宣称覆盖未提供的私有业务场景。

平台协同先核对当前严格 sources DTO 与附件能力，给出可兼容版本化方案。用户要求本轮开发剩余 RAG 项并给出平台方案，不擅自合并平台同事未提交修改或启用生产上传。联验使用有归属的隔离资源，实际 Worker／浏览器与授权桩分开记录。

任务、执行证据与接口方案分别见 [tasks](tasks.md)、[verification](verification.md)、[平台协同方案](platform-contract.md)。

## 已完成结果

- Ubuntu 在线接收 MD／TXT／PDF／DOCX／PPTX／PNG／JPEG；多模态格式仅在 documents 依赖齐全、Docling 和图像／表格／公式处理启用时声明，20MiB 上限及容器校验保留。
- 受管资产、完整成果签名／hash、冻结快照恢复、CAS 与回退；损坏资产拒绝，旧图不重复解析或调用模型。
- 五类复杂格式独立入库→发布→鉴权 HTTP MCP 全通过，13 个正文／表格／公式／图片事实均命中，首次失败证据保留。
- 临时平台真实普通成员上传 PDF→root 审批→后台 ready，另一成员查询 MD／PDF／DOCX／PPTX，撤权／Stop／重启／Fork／重复零新增调用已验。
- 通用公开合成资料最终 19 题基线：16 道有答案 Recall@8 与证据完整率 100%，检索 P50／P95 为 2.948／3.564 秒；3 类 Agent 无答案拒答与跨项目隔离通过。
- 20MiB 双页 PDF、两项目排队且旧库可查、30 次确定性快照观测通过；这不是生产吞吐上限，费用金额未知保留 null。

平台主工作区没有直接合并本次联验代码。动态格式、可信 FileRef 文本投影、root ToolNode 与回执等临时修复见 [补丁](platform-integration.patch) 和 [基线说明](platform-patch-context.json)。补丁依赖原知识专项已接入的 union 基线，不能对当前主工作区盲目套用。平台来源 v2 展示和图片 ImageRef 收据的具体后续方案见 [平台协同](platform-contract.md)；音视频按用户决定延期。

交付记录见 [delivery.json](delivery.json)；Ubuntu 工作分支跟踪同名 origin 分支，现役 main 不擅自合并。
