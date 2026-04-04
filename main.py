import asyncio

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import MessageChain


class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.last_players: set = set()
        self._monitor_task = None
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def initialize(self):
        self._session = aiohttp.ClientSession()
        await self._refresh_token()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("[Terraria] 监控任务已启动")

    def _allowed(self, event: AstrMessageEvent) -> bool:
        group_ids = self.config.get("group_ids", [])
        return event.get_group_id() in group_ids

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        admin_ids = self.config.get("admin_ids", [])
        if not admin_ids:
            return False
        return event.get_sender_id() in admin_ids

    async def _refresh_token(self) -> bool:
        host = self.config.get("tshock_host", "")
        username = self.config.get("tshock_username", "")
        password = self.config.get("tshock_password", "")
        if not host or not username or not password:
            logger.warning("[Terraria] TShock 连接信息未配置")
            return False
        url = f"{host}/token/create"
        try:
            async with self._session.get(
                url, params={"username": username, "password": password}
            ) as resp:
                data = await resp.json(content_type=None)
                if str(data.get("status")) == "200":
                    self._token = data["token"]
                    logger.info(f"[Terraria] Token 获取成功: {self._token[:8]}...")
                    return True
                logger.error(f"[Terraria] Token 获取失败: {data}")
                return False
        except Exception as e:
            logger.error(f"[Terraria] Token 请求异常: {e}")
            return False

    async def _get_status(self) -> dict | None:
        host = self.config.get("tshock_host", "")
        url = f"{host}/v2/server/status"
        try:
            async with self._session.get(
                url, params={"token": self._token, "players": "true"}
            ) as resp:
                data = await resp.json(content_type=None)
                if str(data.get("status")) == "403":
                    self._token = None
                    return None
                return data
        except Exception as e:
            logger.error(f"[Terraria] 状态请求异常: {e}")
            return None

    async def _exec_command(self, cmd: str) -> dict | None:
        host = self.config.get("tshock_host", "")
        url = f"{host}/v3/server/rawcmd"
        try:
            async with self._session.get(
                url, params={"token": self._token, "cmd": cmd}
            ) as resp:
                return await resp.json(content_type=None)
        except Exception as e:
            logger.error(f"[Terraria] 命令请求异常: {e}")
            return None

    async def _send_to_groups(self, message: str):
        session_ids = self.config.get("session_ids", [])
        for session_id in session_ids:
            try:
                await self.context.send_message(
                    session_id, MessageChain().message(message)
                )
            except Exception as e:
                logger.error(f"[Terraria] 推送到 {session_id} 失败: {e}")

    async def _poll(self):
        if not self._token:
            ok = await self._refresh_token()
            if not ok:
                return

        status = await self._get_status()
        if not status or str(status.get("status")) != "200":
            return

        current_players = {
            p.get("nickname", "").strip()
            for p in status.get("players", [])
            if p.get("nickname", "").strip()
        }

        joined = current_players - self.last_players
        left = self.last_players - current_players

        if not self.config.get("notify_join_leave", True):
            self.last_players = current_players
            return

        for name in joined:
            count = len(current_players)
            names = "、".join(sorted(current_players))
            await self._send_to_groups(
                f"🟢 {name} 加入了服务器。\n在线: {count} 人\n{names}"
            )

        for name in left:
            count = len(current_players)
            if current_players:
                names = "、".join(sorted(current_players))
                msg = f"🔴 {name} 离开了服务器。\n在线: {count} 人\n{names}"
            else:
                msg = f"🔴 {name} 离开了服务器。\n在线: 0 人\n暂无玩家"
            await self._send_to_groups(msg)

        self.last_players = current_players

    async def _monitor_loop(self):
        poll_interval = self.config.get("poll_interval", 15)
        while True:
            try:
                await self._poll()
            except Exception as e:
                logger.error(f"[Terraria] 轮询错误: {e}")
            await asyncio.sleep(poll_interval)

    @filter.command("ss")
    async def cmd_status(self, event: AstrMessageEvent):
        if not self._allowed(event):
            return
        if not self._token:
            await self._refresh_token()
        status = await self._get_status()
        if status and str(status.get("status")) == "200":
            players = [p.get("nickname", "").strip() for p in status.get("players", [])]
            players = [n for n in players if n]
            count = len(players)
            msg = (
                f"👥 在线: {count} 人\n{'、'.join(players) if players else '暂无玩家'}"
            )
        else:
            msg = "⚠️ 无法获取服务器状态"
        yield event.plain_result(msg)

    @filter.command("tc")
    async def cmd_exec(self, event: AstrMessageEvent, cmd: str):
        if not self._allowed(event):
            return
        if not self._is_admin(event):
            yield event.plain_result("⚠️ 你没有权限执行此命令")
            return
        if not self._token:
            await self._refresh_token()
        result = await self._exec_command(f"/{cmd}")
        if result:
            response_text = "\n".join(result.get("response", ["执行完成"]))
            yield event.plain_result(f"📋 执行结果:\n{response_text}")
        else:
            yield event.plain_result("⚠️ 命令执行失败")

    async def destroy(self):
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._session:
            await self._session.close()
        logger.info("[Terraria] 已停止")
