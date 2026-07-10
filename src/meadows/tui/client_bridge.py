"""Bridges MeadowClient events to a thread-safe queue for the curses TUI."""

from __future__ import annotations

import logging
import queue
from typing import Any

from meadows.client import MeadowClient
from meadows.protocol import EventName, JWTClaims

logger = logging.getLogger(__name__)


class AuthData:
    def __init__(self, data: dict[str, Any]) -> None:
        self.user_id: str = data.get("user_id", "")
        self.username: str = data.get("username", "")
        self.groups: list[dict[str, Any]] = data.get("groups", [])
        self.bots: list[dict[str, Any]] = data.get("bots", [])
        self.permissions: list[str] = data.get("permissions", [])
        self.available_permissions: list[str | dict[str, str]] = data.get("available_permissions", [])

    def __repr__(self) -> str:
        return f"AuthData(user_id={self.user_id!r}, username={self.username!r}, groups={len(self.groups)})"


class ClientBridge:
    def __init__(self, event_queue: queue.Queue[tuple[str, dict[str, Any]]], server_url: str) -> None:
        self._queue = event_queue
        self._server_url = server_url
        self._mc: MeadowClient | None = None
        self._auth_data: AuthData | None = None

    @property
    def connected(self) -> bool:
        return self._mc is not None and self._mc.connected

    @property
    def authenticated(self) -> bool:
        return self._mc is not None and self._mc.authenticated

    @property
    def auth_data(self) -> AuthData | None:
        return self._auth_data

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        logger.debug("queue emit: %s (keys=%s)", event, list(data.keys()) if isinstance(data, dict) else type(data))
        self._queue.put((event, data))

    async def connect_with_token(self, token: str) -> None:
        import jwt as pyjwt

        logger.debug("connect_with_token: decoding JWT...")
        claims_dict = pyjwt.decode(token, options={"verify_signature": False})
        claims = JWTClaims(**claims_dict)
        logger.debug("connect_with_token: claims decoded — sub=%s role=%s username=%s exp=%s",
                      claims.sub, claims.role, claims.username, claims.exp)

        if claims.role == "bot":
            logger.warning("token is a bot token (role=bot), TUI expects a user token")

        logger.debug("connect_with_token: creating MeadowClient(server_url=%s)", self._server_url)
        self._mc = MeadowClient(server_url=self._server_url, claims=claims, token=token)
        self._register_handlers()
        self._register_sio_logging()

        logger.debug("connect_with_token: calling sio.connect(%s)", self._server_url)
        await self._mc.connect()
        logger.debug("connect_with_token: sio.connect() returned — transport up, waiting for namespace auth...")

    async def connect_with_secret(self, username: str, jwt_secret: str) -> None:
        from meadows.protocol.jwt import build_claims, JWTRole

        logger.debug("connect_with_secret: building claims for user=%s", username)
        claims = build_claims(name=username, role=JWTRole.USER)
        logger.debug("connect_with_secret: creating MeadowClient(server_url=%s)", self._server_url)
        self._mc = MeadowClient(server_url=self._server_url, claims=claims, jwt_secret=jwt_secret.encode())
        self._register_handlers()
        self._register_sio_logging()

        logger.debug("connect_with_secret: calling sio.connect(%s)", self._server_url)
        await self._mc.connect()
        logger.debug("connect_with_secret: sio.connect() returned — transport up, waiting for namespace auth...")

    def _register_sio_logging(self) -> None:
        if not self._mc:
            return
        self._mc.on_connect(lambda: logger.debug("SIO /chat CONNECT (namespace connected)"))
        self._mc.on_disconnect(lambda: logger.debug("SIO /chat DISCONNECT (namespace disconnected)"))

    def _register_handlers(self) -> None:
        if not self._mc:
            return
        self._mc.on(EventName.AUTHENTICATED, self._on_authenticated)
        self._mc.on(EventName.AUTH_ERROR, self._on_auth_error)
        self._mc.on(EventName.ERROR, self._on_error)
        self._mc.on(EventName.MESSAGE, self._on_message)
        self._mc.on(EventName.USER_TYPING, self._on_user_typing)
        self._mc.on(EventName.JOINED_GROUP, self._on_joined_group)
        self._mc.on(EventName.LEFT_GROUP, self._on_left_group)
        self._mc.on(EventName.USER_JOINED, self._on_user_joined)
        self._mc.on(EventName.USER_LEFT, self._on_user_left)
        self._mc.on(EventName.MEMBERS_UPDATED, self._on_members_updated)
        self._mc.on(EventName.GROUP_CREATED, self._on_group_created)
        self._mc.on(EventName.GROUP_DELETED, self._on_group_deleted)
        self._mc.on(EventName.GROUP_LIST, self._on_group_list)
        self._mc.on(EventName.BOT_LIST, self._on_bot_list)
        self._mc.on(EventName.MESSAGE_REMOVED, self._on_message_removed)
        self._mc.on(EventName.REACTION_ADDED, self._on_reaction_added)
        self._mc.on(EventName.REACTION_TOGGLED, self._on_reaction_toggled)

    async def _on_auth_error(self, data: dict[str, Any]) -> None:
        logger.error("auth_error from server: %s", data)
        self._emit("auth_error", data)

    async def _on_authenticated(self, data: dict[str, Any]) -> None:
        logger.debug("authenticated event received — user_id=%s username=%s groups=%d",
                      data.get("user_id"), data.get("username"), len(data.get("groups", [])))
        self._auth_data = AuthData(data)
        self._emit("authenticated", data)

    async def _on_message(self, data: dict[str, Any]) -> None:
        self._emit("message", data)

    async def _on_user_typing(self, data: dict[str, Any]) -> None:
        self._emit("user_typing", data)

    async def _on_joined_group(self, data: dict[str, Any]) -> None:
        self._emit("joined_group", data)

    async def _on_left_group(self, data: dict[str, Any]) -> None:
        self._emit("left_group", data)

    async def _on_user_joined(self, data: dict[str, Any]) -> None:
        self._emit("user_joined", data)

    async def _on_user_left(self, data: dict[str, Any]) -> None:
        self._emit("user_left", data)

    async def _on_members_updated(self, data: dict[str, Any]) -> None:
        self._emit("members_updated", data)

    async def _on_group_created(self, data: dict[str, Any]) -> None:
        self._emit("group_created", data)

    async def _on_group_deleted(self, data: dict[str, Any]) -> None:
        self._emit("group_deleted", data)

    async def _on_group_list(self, data: dict[str, Any]) -> None:
        self._emit("group_list", data)

    async def _on_bot_list(self, data: dict[str, Any]) -> None:
        self._emit("bot_list", data)

    async def _on_message_removed(self, data: dict[str, Any]) -> None:
        self._emit("message_removed", data)

    async def _on_reaction_added(self, data: dict[str, Any]) -> None:
        self._emit("reaction_added", data)

    async def _on_reaction_toggled(self, data: dict[str, Any]) -> None:
        self._emit("reaction_toggled", data)

    async def _on_error(self, data: dict[str, Any]) -> None:
        self._emit("error", data)

    async def send_message(self, content: str, group_id: str = "general", quoted_message_id: str | None = None) -> None:
        if not self._mc:
            return
        await self._mc.send_message(content=content, group_id=group_id, quoted_message_id=quoted_message_id)

    async def send_typing(self, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.TYPING, {"group_id": group_id})

    async def add_reaction(self, emoji: str, target_message_id: str, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.ADD_REACTION, {
            "emoji": emoji, "target_message_id": target_message_id, "group_id": group_id,
        })

    async def remove_reaction(self, emoji: str, target_message_id: str, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.REMOVE_REACTION, {
            "emoji": emoji, "target_message_id": target_message_id, "group_id": group_id,
        })

    async def join_group(self, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.JOIN_GROUP, {"group_id": group_id})

    async def leave_group(self, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.LEAVE_GROUP, {"group_id": group_id})

    async def create_group(self, group_id: str, name: str | None = None, description: str | None = None) -> None:
        if not self._mc:
            return
        payload: dict[str, Any] = {"group_id": group_id}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        await self._mc.emit(EventName.CREATE_GROUP, payload)

    async def delete_group(self, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.DELETE_GROUP, {"group_id": group_id})

    async def list_groups(self) -> None:
        if not self._mc:
            return
        await self._mc.emit(EventName.LIST_GROUPS, {})

    async def request_bot_jwt(
        self, bot_name: str, permissions: list[str] | None = None, expiry: str | None = None,
    ) -> None:
        if not self._mc:
            return
        payload: dict[str, Any] = {"bot_name": bot_name}
        if permissions:
            payload["permissions"] = permissions
        if expiry:
            payload["expiry"] = expiry
        await self._mc.emit(EventName.REQUEST_BOT_JWT, payload)

    async def disconnect(self) -> None:
        if self._mc:
            await self._mc.disconnect()


class ConnectionFailedError(Exception):
    pass
