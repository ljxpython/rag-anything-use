# 实施方案与范围

用户授权在 sshmy2 解决 pull 冲突并完成剩余 RAG 开发，音视频延期；平台字段／展示给出方案，复杂文档、完整闭环、通用质量及当前资源负载实测。语料按用户答复沿用公开代表性合成资料。

1. 保留 env.example 原改动副本，ff-only 更新主线，Ubuntu 工作分支安装 frozen documents 环境。
2. 保留精确授权、单队列、完整候选和原子激活；校验实际文档容器，持久受管图片与解析成果；失败不隐式 fallback，不污染旧库。
3. 可信页码来自已绑定的 native chunk；默认 sources v1 不变，显式 v2 增加 page／slide／unknown locator。平台 v2 展示与图片收据给出接线方案。
4. 在独立 union 平台组合已有 Token／后台与知识功能，实际普通成员／Worker／浏览器联验；修复只留最小补丁，不擅自提交他人 staged 内容。
5. 公开格式、19 题检索、Agent 无答案／跨项目、20MiB 和两项目排队分别留证；确定性快照压力与真实模型证据分开。费用没有完整费率时金额 null。
6. 全量 RAG 回归、相关平台回归、secret 扫描、文档同步，正常停止所属服务，仅提交推送 Ubuntu 工作分支，供后续验收和合入。

明确后续范围：平台正式合并／上线、v2 前端展示、ImageRef 可信图片上传、音视频、私有业务语料与生产 SLA 不计作本期已部署能力。

实施与验收结果以 [tasks](tasks.md) 和 [verification](verification.md) 为准。
