import asyncio
import hashlib
import json
import time
from typing import Any

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import MessageChain

_TIMEOUT = aiohttp.ClientTimeout(total=10)
_DEFAULT_TOKEN_ENDPOINTS = ("/token/create", "/v2/token/create")
_UNAUTHORIZED_STATUSES = {"401", "403"}
_DEFAULT_TOKEN_LOGIN_COOLDOWN_SECONDS = 300
_NOTIFY_DEDUP_WINDOW_SECONDS = 10
_AUTH_MODE_PASSWORD = "password"
_AUTH_MODE_TOKEN = "token"


class Main(Star):
    """Fork-friendly TShock bridge based on Reisenbug's Terraria manager plugin."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.last_players: set[str] = set()
        self._first_poll = True
        self._monitor_task: asyncio.Task | None = None
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._token_lock = asyncio.Lock()
        self._configured_static_token: str | None = None
        self._static_token_rejected = False
        self._last_token_failure_at = 0.0
        self._recent_notifications: dict[tuple[str, str, str], float] = {}

    async def initialize(self):
        self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        self._sync_static_token_state()
        logger.info("[TShock Bridge] Config summary: %s", "; ".join(self._debug_config_lines()))
        if self._auth_mode() == _AUTH_MODE_TOKEN:
            self._token = self._configured_static_token
            if self._token:
                logger.info("[TShock Bridge] Using configured static token.")
            else:
                logger.warning("[TShock Bridge] auth_mode=token but tshock_token is empty.")
        else:
            await self._refresh_token()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("[TShock Bridge] Monitor task started.")

    def _clean_text(self, value: Any) -> str:
        return str(value).strip() if value is not None else ""

    def _normalize_host(self) -> str:
        return self._clean_text(self.config.get("tshock_host", "")).rstrip("/")

    def _build_url(self, path: str) -> str:
        host = self._normalize_host()
        if not host:
            return ""
        normalized_path = self._clean_text(path)
        if normalized_path.startswith(("http://", "https://")):
            return normalized_path
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        return f"{host}{normalized_path}"

    def _string_id_set(self, key: str) -> set[str]:
        raw_ids = self.config.get(key, [])
        if not isinstance(raw_ids, list):
            return set()
        return {self._clean_text(item) for item in raw_ids if self._clean_text(item)}

    def _token_endpoint_candidates(self) -> list[str]:
        custom = self._clean_text(self.config.get("tshock_token_endpoint", ""))
        candidates: list[str] = []
        if custom:
            candidates.append(custom)
        candidates.extend(_DEFAULT_TOKEN_ENDPOINTS)

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.strip()
            if normalized and normalized not in seen:
                unique.append(normalized)
                seen.add(normalized)
        return unique

    def _sync_static_token_state(self):
        configured = None
        if self._auth_mode() == _AUTH_MODE_TOKEN:
            configured = self._clean_text(self.config.get("tshock_token", "")) or None
        previous = self._configured_static_token
        if configured == self._configured_static_token:
            return
        self._configured_static_token = configured
        self._static_token_rejected = False
        if configured:
            self._token = configured
        elif previous and self._token == previous:
            self._token = None

    def _poll_interval(self) -> int:
        raw_interval = self.config.get("poll_interval", 30)
        try:
            interval = int(raw_interval)
        except (TypeError, ValueError):
            interval = 30
        return max(5, interval)

    def _token_login_cooldown_seconds(self) -> int:
        raw_cooldown = self.config.get(
            "token_login_cooldown", _DEFAULT_TOKEN_LOGIN_COOLDOWN_SECONDS
        )
        try:
            cooldown = int(raw_cooldown)
        except (TypeError, ValueError):
            cooldown = _DEFAULT_TOKEN_LOGIN_COOLDOWN_SECONDS
        return max(0, cooldown)

    def _auth_mode(self) -> str:
        raw_mode = self._clean_text(self.config.get("auth_mode", "")).lower()
        mode_aliases = {
            "password": _AUTH_MODE_PASSWORD,
            "account": _AUTH_MODE_PASSWORD,
            "账号密码": _AUTH_MODE_PASSWORD,
            "token": _AUTH_MODE_TOKEN,
            "static_token": _AUTH_MODE_TOKEN,
            "现成token": _AUTH_MODE_TOKEN,
            "现成 token": _AUTH_MODE_TOKEN,
        }
        if raw_mode:
            return mode_aliases.get(raw_mode, _AUTH_MODE_PASSWORD)

        # Backward compatibility for configs created before auth_mode existed.
        if self._clean_text(self.config.get("tshock_token", "")):
            return _AUTH_MODE_TOKEN
        return _AUTH_MODE_PASSWORD

    def _extract_command_tail(self, event: AstrMessageEvent, command_name: str, fallback: str = "") -> str:
        message_text = self._clean_text(getattr(event, "message_str", ""))
        prefixes = (f"/{command_name}", f"／{command_name}")
        lowered = message_text.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix.lower()):
                return message_text[len(prefix):].strip()
        return fallback.strip()

    def _allowed(self, event: AstrMessageEvent) -> bool:
        return self._clean_text(event.get_group_id()) in self._string_id_set("group_ids")

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        admin_ids = self._string_id_set("admin_ids")
        if not admin_ids:
            return False
        return self._clean_text(event.get_sender_id()) in admin_ids

    def _token_login_cooldown_remaining(self) -> int:
        if not self._last_token_failure_at:
            return 0
        cooldown = self._token_login_cooldown_seconds()
        if cooldown <= 0:
            return 0
        elapsed = time.monotonic() - self._last_token_failure_at
        return max(0, int(cooldown - elapsed))

    def _text_fingerprint(self, value: str) -> str:
        if not value:
            return "empty"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
        first = f"U+{ord(value[0]):04X}"
        last = f"U+{ord(value[-1]):04X}"
        return f"len={len(value)}, first={first}, last={last}, sha256={digest}"

    def _mask_text(self, value: str) -> str:
        if not value:
            return "empty"
        if len(value) == 1:
            return "*"
        if len(value) == 2:
            return f"{value[0]}*"
        return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"

    def _debug_config_lines(self) -> list[str]:
        auth_mode = self._auth_mode()
        username = self._clean_text(self.config.get("tshock_username", ""))
        password = self._clean_text(self.config.get("tshock_password", ""))
        static_token = self._clean_text(self.config.get("tshock_token", ""))
        custom_endpoint = self._clean_text(self.config.get("tshock_token_endpoint", ""))
        configured_sessions = [
            self._clean_text(item)
            for item in self.config.get("session_ids", [])
            if self._clean_text(item)
        ]
        return [
            f"auth_mode={auth_mode}",
            f"host={self._normalize_host() or 'empty'}",
            f"username={self._mask_text(username)} ({self._text_fingerprint(username)})",
            f"password=masked ({self._text_fingerprint(password)})",
            f"static_token={'set' if static_token else 'empty'} ({self._text_fingerprint(static_token)})",
            f"token_endpoint={custom_endpoint or 'auto'}",
            f"endpoint_candidates={','.join(self._token_endpoint_candidates())}",
            f"sessions={len(configured_sessions)} configured/{len(set(configured_sessions))} unique",
            f"local_token={'set' if self._token else 'empty'}",
            f"cooldown_config={self._token_login_cooldown_seconds()}s",
            f"cooldown_remaining={self._token_login_cooldown_remaining()}s",
        ]

    async def _request_json(
        self, url: str, params: dict[str, str] | None = None
    ) -> tuple[int | None, dict[str, Any] | None]:
        if not self._session:
            return None, None
        try:
            async with self._session.get(url, params=params) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    logger.error(
                        "[TShock Bridge] Non-JSON response from %s: %s",
                        url,
                        text[:200],
                    )
                    return resp.status, None
                return resp.status, data
        except Exception as exc:
            logger.error("[TShock Bridge] Request failed for %s: %s", url, exc)
            return None, None

    def _invalidate_token(self, source: str):
        if self._configured_static_token and self._token == self._configured_static_token:
            self._static_token_rejected = True
            logger.error(
                "[TShock Bridge] The configured static token was rejected by %s. "
                "Please update tshock_token.",
                source,
            )
        elif self._token:
            logger.warning(
                "[TShock Bridge] Token was rejected by %s. The plugin will re-login on the next request.",
                source,
            )
        self._token = None

    async def _ensure_token(self) -> bool:
        self._sync_static_token_state()
        if self._token:
            return True

        if self._auth_mode() == _AUTH_MODE_TOKEN:
            if self._static_token_rejected:
                return False
            if not self._configured_static_token:
                logger.warning("[TShock Bridge] auth_mode=token but tshock_token is empty.")
                return False
            self._token = self._configured_static_token
            return True

        cooldown_remaining = self._token_login_cooldown_remaining()
        if cooldown_remaining > 0:
            return False

        async with self._token_lock:
            if self._token:
                return True
            if self._token_login_cooldown_remaining() > 0:
                return False
            return await self._refresh_token()

    async def _refresh_token(self) -> bool:
        host = self._normalize_host()
        username = self._clean_text(self.config.get("tshock_username", ""))
        password = self._clean_text(self.config.get("tshock_password", ""))
        if not host:
            logger.warning("[TShock Bridge] tshock_host is not configured.")
            return False
        if not username or not password:
            logger.warning(
                "[TShock Bridge] TShock username/password is missing. "
                "You can also fill tshock_token to bypass token login."
            )
            return False

        attempts: list[str] = []
        for endpoint in self._token_endpoint_candidates():
            url = self._build_url(endpoint)
            status_code, data = await self._request_json(
                url,
                params={"username": username, "password": password},
            )
            if data and str(data.get("status")) == "200" and data.get("token"):
                self._token = self._clean_text(data.get("token"))
                self._last_token_failure_at = 0.0
                logger.info("[TShock Bridge] Token fetched successfully via %s.", endpoint)
                return True

            attempts.append(
                f"{endpoint} -> http={status_code}, body={data if data is not None else 'null'}"
            )

            api_status = self._clean_text(data.get("status")) if data else ""
            if status_code in (401, 403) or api_status in _UNAUTHORIZED_STATUSES:
                break

        self._last_token_failure_at = time.monotonic()
        cooldown = self._token_login_cooldown_seconds()
        logger.error(
            "[TShock Bridge] Failed to fetch token. Tried: %s. "
            "TShock returns the same 403 for bad credentials, missing tshock.rest.useapi, "
            "and REST login rate limiting. The plugin will cool down for %ss before retrying. "
            "Set tshock_token to bypass token login.",
            " | ".join(attempts) if attempts else "no endpoint",
            cooldown,
        )
        return False

    async def _get_status(self) -> dict[str, Any] | None:
        url = self._build_url("/v2/server/status")
        status_code, data = await self._request_json(
            url,
            params={"token": self._token or "", "players": "true"},
        )
        if not data:
            return None

        api_status = self._clean_text(data.get("status"))
        if status_code in (401, 403) or api_status in _UNAUTHORIZED_STATUSES:
            self._invalidate_token("/v2/server/status")
            return None
        return data

    async def _exec_command(self, cmd: str) -> dict[str, Any] | None:
        url = self._build_url("/v3/server/rawcmd")
        status_code, data = await self._request_json(
            url,
            params={"token": self._token or "", "cmd": cmd},
        )
        if not data:
            return None

        api_status = self._clean_text(data.get("status"))
        if status_code in (401, 403) or api_status in _UNAUTHORIZED_STATUSES:
            self._invalidate_token("/v3/server/rawcmd")
            return None
        return data

    def _deduped_session_ids(self) -> list[str]:
        session_ids = self.config.get("session_ids", [])
        if not isinstance(session_ids, list):
            return []
        deduped: list[str] = []
        seen: set[str] = set()
        for session_id in session_ids:
            normalized = self._clean_text(session_id)
            if not normalized or normalized in seen:
                continue
            deduped.append(normalized)
            seen.add(normalized)
        return deduped

    def _should_send_notification(self, session_id: str, action: str, player: str) -> bool:
        now = time.monotonic()
        expired_keys = [
            key
            for key, timestamp in self._recent_notifications.items()
            if now - timestamp > _NOTIFY_DEDUP_WINDOW_SECONDS
        ]
        for key in expired_keys:
            self._recent_notifications.pop(key, None)

        key = (session_id, action, player)
        if key in self._recent_notifications:
            return False
        self._recent_notifications[key] = now
        return True

    async def _send_to_groups(self, message: str, action: str = "message", player: str = ""):
        for normalized in self._deduped_session_ids():
            if not self._should_send_notification(normalized, action, player):
                logger.debug(
                    "[TShock Bridge] Duplicate notification skipped: %s/%s/%s",
                    normalized,
                    action,
                    player,
                )
                continue
            try:
                await self.context.send_message(
                    normalized, MessageChain().message(message)
                )
            except Exception as exc:
                logger.error("[TShock Bridge] Failed to push to %s: %s", normalized, exc)

    def _parse_players(self, status: dict[str, Any]) -> set[str]:
        players = status.get("players")
        if not isinstance(players, list):
            return set()

        normalized_players: set[str] = set()
        for player in players:
            if isinstance(player, dict):
                name = self._clean_text(
                    player.get("nickname") or player.get("name") or player.get("username")
                )
            else:
                name = self._clean_text(player)
            if name:
                normalized_players.add(name)
        return normalized_players

    def _format_players(self, players: set[str]) -> str:
        if not players:
            return "暂无玩家"
        return "、".join(sorted(players))

    async def _poll(self):
        if not await self._ensure_token():
            return

        status = await self._get_status()
        if not status or self._clean_text(status.get("status")) != "200":
            return

        current_players = self._parse_players(status)

        if self._first_poll:
            self.last_players = current_players
            self._first_poll = False
            return

        if not self.config.get("notify_join_leave", True):
            self.last_players = current_players
            return

        joined = current_players - self.last_players
        left = self.last_players - current_players

        for name in sorted(joined):
            await self._send_to_groups(
                f"[上线] {name} 加入了服务器\n"
                f"在线: {len(current_players)} 人\n"
                f"{self._format_players(current_players)}",
                action="join",
                player=name,
            )

        for name in sorted(left):
            await self._send_to_groups(
                f"[下线] {name} 离开了服务器\n"
                f"在线: {len(current_players)} 人\n"
                f"{self._format_players(current_players)}",
                action="leave",
                player=name,
            )

        self.last_players = current_players

    async def _monitor_loop(self):
        while True:
            try:
                await self._poll()
            except Exception as exc:
                logger.error("[TShock Bridge] Poll loop error: %s", exc)
            await asyncio.sleep(self._poll_interval())

    @filter.command("ss")
    async def cmd_status(self, event: AstrMessageEvent):
        if not self._allowed(event):
            return

        if not await self._ensure_token():
            yield event.plain_result("无法连接到 TShock REST API。")
            return

        status = await self._get_status()
        if not status or self._clean_text(status.get("status")) != "200":
            yield event.plain_result("无法获取服务器状态。")
            return

        players = self._parse_players(status)
        player_count = self._clean_text(status.get("playercount")) or str(len(players))
        max_players = self._clean_text(status.get("maxplayers")) or "?"
        world = self._clean_text(status.get("world")) or "未知世界"
        server_version = self._clean_text(status.get("serverversion")) or "未知版本"
        message = (
            f"世界: {world}\n"
            f"版本: {server_version}\n"
            f"在线: {player_count}/{max_players}\n"
            f"玩家: {self._format_players(players)}"
        )
        yield event.plain_result(message)

    @filter.command("tc")
    async def cmd_exec(self, event: AstrMessageEvent, cmd: str = ""):
        if not self._allowed(event):
            return
        if not self._is_admin(event):
            yield event.plain_result("你没有权限执行这个命令。")
            return

        normalized_cmd = self._extract_command_tail(event, "tc", cmd)
        if not normalized_cmd:
            yield event.plain_result("用法: /tc <命令>")
            return

        if not await self._ensure_token():
            yield event.plain_result("无法连接到 TShock REST API。")
            return

        result = await self._exec_command(f"/{normalized_cmd}")
        if not result and await self._ensure_token():
            result = await self._exec_command(f"/{normalized_cmd}")

        if not result:
            yield event.plain_result("命令执行失败。")
            return

        response = result.get("response", [])
        if isinstance(response, list):
            response_text = "\n".join(
                self._clean_text(item) for item in response if self._clean_text(item)
            )
        else:
            response_text = self._clean_text(response)
        yield event.plain_result(
            f"执行结果:\n{response_text or '服务器已接受命令，但没有返回额外文本。'}"
        )

    @filter.command("tsdebug")
    async def cmd_debug(self, event: AstrMessageEvent, action: str = ""):
        if not self._allowed(event):
            return
        if not self._is_admin(event):
            yield event.plain_result("你没有权限执行这个命令。")
            return

        normalized_action = action.strip().lower()
        lines = ["TShock Bridge 诊断:", *self._debug_config_lines()]

        if normalized_action in {"login", "test", "force"}:
            self._last_token_failure_at = 0.0
            self._token = None
            ok = await self._refresh_token()
            lines.append(f"manual_login={'success' if ok else 'failed'}")
            lines.append(f"cooldown_remaining_after={self._token_login_cooldown_remaining()}s")
        else:
            lines.append("提示: 使用 /tsdebug login 可强制测试账号密码申请 token。")

        yield event.plain_result("\n".join(lines))

    async def destroy(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
        logger.info("[TShock Bridge] Plugin stopped.")
