# AstrBot TShock Bridge

一个面向 AstrBot 的 TShock 服务器桥接插件，用于推送 Terraria 玩家上下线、查询在线状态，以及远程执行 TShock 命令。

本版本基于原插件 [Reisenbug/AstrBot_Plugin_Terraria_Server_Manager](https://github.com/Reisenbug/AstrBot_Plugin_Terraria_Server_Manager) 改造，主要做了这些调整：

- 改名为 `astrbot_plugin_tshock_bridge`，避免和上游同名时配置文件冲突
- 补充 `tshock_token` 静态 token 模式，便于绕过部分服务器对 `token/create` 登录的兼容问题
- 增加账号登录失败冷却，避免反复请求触发 TShock REST 登录限流
- 重写配置说明、日志文案和状态输出，方便排查问题

当前 fork 仓库：
[Whereis-Alice/astrbot_plugin_tshock_bridge](https://github.com/Whereis-Alice/astrbot_plugin_tshock_bridge)

## 功能

- 推送玩家上下线通知到指定群聊
- 使用 `/ss` 查看在线玩家和世界状态
- 使用 `/tc <命令>` 远程执行 TShock 命令
- 同时兼容 `/token/create` 和 `/v2/token/create`
- 支持手动填入现成 token

## 配置项

| 配置项 | 说明 |
| --- | --- |
| `tshock_host` | TShock REST API 地址，包含端口，例如 `http://1.2.3.4:7878` |
| `tshock_username` | TShock REST API 用户名 |
| `tshock_password` | TShock REST API 密码 |
| `tshock_token` | 可选。手动填写现成 token。填写后优先使用，不再依赖登录接口 |
| `tshock_token_endpoint` | 可选。自定义 token 获取路径，例如 `/token/create` |
| `session_ids` | 接收通知的 AstrBot session ID 列表 |
| `group_ids` | 允许使用插件命令的群 ID 列表 |
| `admin_ids` | 允许执行 `/tc` 的管理员 ID 列表 |
| `notify_join_leave` | 是否推送上下线通知 |
| `poll_interval` | 轮询间隔，单位秒 |

说明：`tshock_token_endpoint` 一般不用填，保持为空即可。正常账号密码登录时，密码应该填写在 `tshock_password`。

## 静态 Token

如果你的 TShock 服务器对用户名密码登录不稳定，可以先手动取 token，再填到 `tshock_token`：

```bash
curl -G 'http://your-host:port/token/create' \
  --data-urlencode 'username=你的用户名' \
  --data-urlencode 'password=你的密码'
```

拿到返回 JSON 里的 `token` 后，填入插件配置即可。填写 `tshock_token` 后，插件会优先使用静态 token，不再调用 `/token/create` 登录接口。

## 登录 403

TShock 的 `/token/create` 可能会把多种情况都返回成同一句 403：账号不存在、密码错误、用户组缺少 `tshock.rest.useapi` 权限、同一 IP 的 REST 登录请求桶触发限流。

账号登录失败后，本插件会冷却 5 分钟再重试，并且遇到 401/403 后不会继续请求第二个 token 端点，避免把云服务器 IP 更快打进 TShock 限流桶。

如果要使用账号密码登录，请确认 TShock 账号所在组拥有：

```text
tshock.rest.useapi
```

如果要使用 `/tc <命令>` 远程执行命令，还需要：

```text
tshock.rest.command
```

同时，TShock 仍会检查被执行命令本身所需的权限。

## 指令

- `/ss` 查看服务器在线状态
- `/tc <命令>` 远程执行 TShock 命令，例如 `/tc who`

## 说明

- 这个 fork 保留了上游的基础交互方式，但插件名、配置名和说明文案已经改成新的标识
- 建议云端只保留 `astrbot_plugin_tshock_bridge`，禁用旧的 `astrbot_plugin_terraria_server_manager`，避免两份插件同时轮询同一个 TShock REST API
