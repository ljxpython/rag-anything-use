# 星河系统接口规范

登录接口为 POST /v2/auth/login，成功响应字段为 access_token 和 expires_in。访问令牌有效期为 90 分钟；刷新令牌有效期为 10 天。

客户端必须使用 HTTPS。超过限流额度返回 HTTP 429，响应头 Retry-After 给出等待秒数。单个客户端每分钟最多发送 240 次请求。

创建订单使用 POST /v2/orders。创建订单的幂等键通过 Idempotency-Key 头传递，同一幂等键的重放保留时间为 36 小时。

删除令牌使用 DELETE /v2/auth/token，成功返回 HTTP 204。刷新令牌与备份保留时间属于不同概念。本规范没有说明合同价格或员工薪资。
