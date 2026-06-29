# AstrBot TShock Bridge

一个面向 AstrBot 的 TShock 服务器桥接插件，用于推送 Terraria 玩家上下线、查询在线状态，以及远程执行 TShock 命令。

本插件基于 [Reisenbug/AstrBot_Plugin_Terraria_Server_Manager](https://github.com/Reisenbug/AstrBot_Plugin_Terraria_Server_Manager) 改造，当前 fork 仓库为 [Whereis-Alice/astrbot_plugin_tshock_bridge](https://github.com/Whereis-Alice/astrbot_plugin_tshock_bridge)。

## 功能

- `/ss` 查看服务器状态和在线玩家
- `/tc <命令>` 远程执行 TShock 命令
- 玩家上下线通知推送到指定群聊
- 支持两种认证模式：账号密码自动申请 token、直接使用现成 token
- 登录失败冷却，避免反复触发 TShock REST 登录限流

## 认证模式

配置项 `auth_mode` 二选一：

| 模式 | 说明 | 需要填写 |
| --- | --- | --- |
| `password` | 使用 TShock 用户名/密码自动申请 token | `tshock_username`、`tshock_password` |
| `token` | 直接使用现成 TShock token | `tshock_token` |

说明：TShock REST 的状态查询和命令接口最终都需要 token。`password` 模式会先调用 token 接口申请 token，再用申请到的 token 工作；`token` 模式则跳过账号密码登录。

## 主要配置

| 配置项 | 说明 |
| --- | --- |
| `tshock_host` | REST API 地址，例如 `http://1.2.3.4:7878` |
| `auth_mode` | `password` 或 `token` |
| `tshock_username` | TShock 用户名，`password` 模式使用 |
| `tshock_password` | TShock 密码，`password` 模式使用 |
| `tshock_token` | 现成 token，`token` 模式使用 |
| `tshock_token_endpoint` | token 接口路径，默认 `/token/create` |
| `session_ids` | 通知目标 session ID 列表 |
| `group_ids` | 允许使用插件命令的群 ID |
| `admin_ids` | 允许使用 `/tc` 和 `/tsdebug` 的管理员 ID |
| `notify_join_leave` | 是否推送上下线通知 |
| `poll_interval` | 轮询间隔，单位秒 |

## 取 Token

如果选择 `token` 模式，可以手动取 token 后填到 `tshock_token`：

```bash
curl -G 'http://your-host:port/token/create' \
  --data-urlencode 'username=你的用户名' \
  --data-urlencode 'password=你的密码'
```

## 登录 403

TShock 的 `/token/create` 会把多种情况都返回成同一句 403：账号不存在、密码错误、用户组缺少 `tshock.rest.useapi`、同一 IP 的 REST 登录请求桶触发限流。

如果要使用 `password` 模式，请确认账号所在组拥有：

```text
tshock.rest.useapi
```

如果要使用 `/tc <命令>`，还需要：

```text
tshock.rest.command
```

`superadmin` 组会天然拥有权限，但仍可能被 REST 登录限流影响。

## 指令

- `/ss` 查看服务器在线状态
- `/tc <命令>` 远程执行 TShock 命令，例如 `/tc who`
- `/tsdebug` 查看插件读取到的配置摘要，不输出完整密码或完整 token
- `/tsdebug login` 强制测试一次账号密码申请 token

## 说明

- 这个 fork 保留了上游的基础交互方式，但插件名、配置名和说明文案已经改成新的标识
- 建议云端只保留 `astrbot_plugin_tshock_bridge`，禁用旧的 `astrbot_plugin_terraria_server_manager`
