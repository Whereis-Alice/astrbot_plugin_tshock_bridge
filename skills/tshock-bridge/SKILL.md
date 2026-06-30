---
name: tshock-bridge
description: Use when the user asks about Terraria/TShock server status or asks the bot to operate the TShock server through TShock Bridge tools.
---

# TShock Bridge

Use this skill when the user asks about the Terraria/TShock server, online players, server status, or wants the bot to run a TShock command.

## Available Tools

- Use `tshock_server_status` for questions like "服务器有人吗", "谁在线", "查一下泰拉瑞亚状态", or "TShock 状态怎么样".
- Use `tshock_run_command` only when the user clearly asks the bot to operate the TShock server or run a specific TShock command.

## Command Rules

- Pass commands to `tshock_run_command` without the chat prefix `/tc`.
- Prefer commands without the leading slash, for example `who`, `help`, `apm l`, or `time noon`.
- If the user already wrote a slash command, remove only the command prefix used for chatting. For example `/tc apm l` becomes `apm l`; `/who` can be sent as `who`.
- Do not invent plugin IDs or command arguments. If the user asks to install, uninstall, or update an APM plugin but the target is unclear, list plugins first with `apm l` and ask the user to confirm the exact target.

## Safety

- Destructive or disruptive commands require explicit user confirmation before execution.
- Examples that need confirmation include ban, unban, kick, mute, unmute, kill, butcher, off, exit, restart, reload, `apm i`, `apm install`, `apm u`, `apm uninstall`, and `apm update`.
- If a tool response says confirmation is required, explain the risk briefly and ask the user to confirm before calling the tool again with `confirmed=true`.
- If a permission error is returned, tell the user the current chat or sender is not in the plugin whitelist instead of retrying.

## Response Style

- Summarize tool results in natural language.
- Keep raw command output when it is useful, especially for plugin lists, player lists, or errors from TShock.
- Do not expose configured tokens, passwords, or hidden plugin configuration values.
