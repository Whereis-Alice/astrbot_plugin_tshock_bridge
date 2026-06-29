# AstrBot TShock Bridge

一个面向 AstrBot 的 TShock 服务器桥接插件，用于推送 Terraria 玩家上下线、查询在线状态，以及远程执行 TShock 命令。

这个版本基于原插件 [Reisenbug/AstrBot_Plugin_Terraria_Server_Manager](https://github.com/Reisenbug/AstrBot_Plugin_Terraria_Server_Manager) 改造，主要做了三件事：

- 改名为 `astrbot_plugin_tshock_bridge`，避免和上游同名时配置文件冲突
- 补充 `tshock_token` 静态 token 模式，便于绕过部分服务器对 `token/create` 登录的兼容问题
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

## 静态 token 用法

如果你的 TShock 服务器对用户名密码登录不稳定，可以先手动取 token，再填到 `tshock_token`：

```bash
curl -G 'http://your-host:port/token/create' \
  --data-urlencode 'username=你的用户名' \
  --data-urlencode 'password=你的密码'
```

拿到返回 JSON 里的 `token` 后，填入插件配置即可。

## 指令

- `/ss`
  查看服务器在线状态
- `/tc <命令>`
  远程执行 TShock 命令，例如 `/tc who`

## 说明

- 这个 fork 当前仍然保留了上游的基础交互方式，但插件名、配置名和说明文档已经改成了新的标识
- 你 fork 到自己的仓库后，建议把 `metadata.yaml` 里的 `repo` 改成你的仓库地址
