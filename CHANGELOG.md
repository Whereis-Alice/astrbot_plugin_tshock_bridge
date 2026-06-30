# Changelog

本项目基于 [Reisenbug/AstrBot_Plugin_Terraria_Server_Manager](https://github.com/Reisenbug/AstrBot_Plugin_Terraria_Server_Manager) 改造。

## 0.3.1

- 新增 `token_login_cooldown` 配置项，可调整账号密码申请 token 失败后的重试冷却秒数。
- 支持将 `token_login_cooldown` 设置为 `0` 来关闭登录失败冷却。
- 冷却期间不再反复输出 `Token login is cooling down` 警告日志，仅在登录失败时说明冷却时间。

## 0.3.0

- 新增 `auth_mode` 认证模式，支持 `password` 和 `token` 二选一。
- `password` 模式使用 TShock 用户名/密码自动申请 token。
- `token` 模式直接使用现成 TShock token，不再调用账号密码登录接口。
- 缩短 `_conf_schema.json` 中的配置项描述，减少 AstrBot WebUI 配置页文字过长的问题。
- 将 `tshock_token_endpoint` 默认值设为 `/token/create`。

## 0.2.4

- 新增 `/tsdebug` 管理员诊断命令，显示插件读取到的安全配置摘要。
- 新增 `/tsdebug login`，用于手动测试账号密码申请 token。
- 诊断输出使用长度、首尾字符和 SHA-256 前缀，不输出完整密码或完整 token。

## 0.2.3

- 修复中文文案乱码问题。
- 增加账号密码登录失败冷却，避免反复触发 TShock REST 登录限流。
- 遇到 401/403 后不再继续尝试第二个 token 端点，减少限流风险。
- README 补充 TShock `/token/create` 403 的常见原因说明。

## 0.2.2

- 修复 AstrBot 配置页中 `tshock_password` 和 `tshock_token` 字段被隐藏的问题。
- 调整配置说明，便于在 WebUI 中填写密码和 token。

## 0.2.0

- 插件重命名为 `astrbot_plugin_tshock_bridge`。
- 元数据改为 `Whereis-Alice/astrbot_plugin_tshock_bridge`。
- 新增 `tshock_token` 静态 token 支持。
- 兼容 `/token/create` 和 `/v2/token/create`。
- 优化 TShock REST API 错误日志，便于排查登录失败原因。
