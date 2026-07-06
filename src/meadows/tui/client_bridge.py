"""Bridges MeadowClient events to Textual message passing."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from textual import messages as text_messages
from textual.app import App

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
        self.available_permissions: list[str] = data.get("available_permissions", [])

    def __repr__(self) -> str:
        return f"AuthData(user_id={self.user_id!r}, username={self.username!r}, groups={len(self.groups)})"


class ClientBridge:
    def __init__(self, app: App, server_url: str) -> None:
        self._app = app
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

    async def connect_with_token(self, token: str) -> None:
        import jwt as pyjwt

        logger.info("connecting with token to %s", self._server_url)

        try:
            claims_dict = pyjwt.decode(token, options={"verify_signature": False})
            logger.debug("decoded claims: %s", claims_dict)
        except Exception as exc:
            logger.error("failed to decode token: %s", exc)
            raise ConnectionFailedError(f"Invalid JWT: {exc}") from exc

        claims = JWTClaims(**claims_dict)
        logger.debug("parsed claims: sub=%s role=%s", claims.sub, claims.role)

        if claims.role == "bot":
            logger.warning("token is a bot token (role=bot), TUI expects a user token")

        self._mc = MeadowClient(
            server_url=self._server_url,
            claims=claims,
            token=token,
        )
        self._register_handlers()
        self._register_sio_logging()

        logger.info("connecting socket.io to %s/chat", self._server_url)
        try:
            await self._mc.connect()
            logger.info("socket.io transport connected, awaiting auth...")
        except Exception as exc:
            logger.error("socket.io connect failed: %s", exc)
            raise ConnectionFailedError(f"Socket.IO connect failed: {exc}") from exc

    async def connect_with_secret(self, username: str, jwt_secret: str) -> None:
        from meadows.protocol.jwt import build_claims, JWTRole

        logger.info("connecting with secret as %s to %s", username, self._server_url)
        claims = build_claims(name=username, role=JWTRole.USER)
        logger.debug("built claims: sub=%s", claims.sub)

        self._mc = MeadowClient(
            server_url=self._server_url,
            claims=claims,
            jwt_secret=jwt_secret.encode(),
        )
        self._register_handlers()
        self._register_sio_logging()

        try:
            await self._mc.connect()
            logger.info("socket.io transport connected, awaiting auth for %s...", username)
        except Exception as exc:
            logger.error("socket.io connect failed: %s", exc)
            raise ConnectionFailedError(f"Socket.IO connect failed: {exc}") from exc

    def _register_sio_logging(self) -> None:
        if not self._mc:
            return
        self._mc.on_connect(lambda: logger.debug("SIO /chat namespace connected"))
        self._mc.on_disconnect(lambda: logger.debug("SIO /chat namespace disconnected"))

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

    async def _post_message(self, msg_type: type, data: Any) -> None:
        with contextlib.suppress(Exception):
            self._app.post_message(msg_type(data))

    async def _on_auth_error(self, data: dict[str, Any]) -> None:
        error = data.get("error", str(data))
        logger.error("auth error from server: %s", error)
        await self._post_message(AuthFailed, {"error": error})

    async def _on_authenticated(self, data: dict[str, Any]) -> None:
        self._auth_data = AuthData(data)
        logger.info("authenticated as %s (user_id=%s)", self._auth_data.username, self._auth_data.user_id)
        logger.debug("auth data: %s", self._auth_data)
        await self._post_message(Authenticated, data)

    async def _on_message(self, data: dict[str, Any]) -> None:
        await self._post_message(ChatMessage, data)

    async def _on_user_typing(self, data: dict[str, Any]) -> None:
        await self._post_message(UserTyping, data)

    async def _on_joined_group(self, data: dict[str, Any]) -> None:
        await self._post_message(JoinedGroup, data)

    async def _on_left_group(self, data: dict[str, Any]) -> None:
        await self._post_message(LeftGroup, data)

    async def _on_user_joined(self, data: dict[str, Any]) -> None:
        await self._post_message(UserJoined, data)

    async def _on_user_left(self, data: dict[str, Any]) -> None:
        await self._post_message(UserLeft, data)

    async def _on_members_updated(self, data: dict[str, Any]) -> None:
        await self._post_message(MembersUpdated, data)

    async def _on_group_created(self, data: dict[str, Any]) -> None:
        await self._post_message(GroupCreated, data)

    async def _on_group_deleted(self, data: dict[str, Any]) -> None:
        await self._post_message(GroupDeleted, data)

    async def _on_group_list(self, data: dict[str, Any]) -> None:
        await self._post_message(GroupList, data)

    async def _on_bot_list(self, data: dict[str, Any]) -> None:
        await self._post_message(BotList, data)

    async def _on_message_removed(self, data: dict[str, Any]) -> None:
        await self._post_message(MessageRemoved, data)

    async def _on_reaction_added(self, data: dict[str, Any]) -> None:
        await self._post_message(ReactionAdded, data)

    async def _on_reaction_toggled(self, data: dict[str, Any]) -> None:
        await self._post_message(ReactionToggled, data)

    async def _on_error(self, data: dict[str, Any]) -> None:
        logger.warning("server error: %s", data)
        await self._post_message(ServerError, data)

    async def send_message(
        self, content: str, group_id: str = "general", quoted_message_id: str | None = None
    ) -> None:
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
        await self._mc.emit(
            EventName.ADD_REACTION,
            {"emoji": emoji, "target_message_id": target_message_id, "group_id": group_id},
        )

    async def remove_reaction(self, emoji: str, target_message_id: str, group_id: str) -> None:
        if not self._mc:
            return
        await self._mc.emit(
            EventName.REMOVE_REACTION,
            {"emoji": emoji, "target_message_id": target_message_id, "group_id": group_id},
        )

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
        self, bot_name: str, permissions: list[str] | None = None, expiry: str | None = None
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


class Authenticated(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class AuthFailed(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class ServerError(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class ChatMessage(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class UserTyping(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class JoinedGroup(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class LeftGroup(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class UserJoined(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class UserLeft(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class MembersUpdated(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class GroupCreated(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class GroupDeleted(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class GroupList(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class BotList(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class MessageRemoved(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class ReactionAdded(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()


class ReactionToggled(text_messages.Message):
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        super().__init__()
