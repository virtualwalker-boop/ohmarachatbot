import redis.asyncio as redis
from enum import Enum
from core.config import settings
import json

class UserState(str, Enum):
    IDLE = "IDLE"
    FAQ_LOOP = "FAQ_LOOP"
    COLLECTING_BOOKING_INFO = "COLLECTING_BOOKING_INFO"
    ESTIMATING_COST = "ESTIMATING_COST"
    QUOTATION_GENERATED = "QUOTATION_GENERATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"

class StateMachine:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    def _get_key(self, psid: str) -> str:
        return f"fsm:user:{psid}"

    async def get_state(self, psid: str) -> UserState:
        data = await self.redis.get(self._get_key(psid))
        if data:
            try:
                state_data = json.loads(data)
                return UserState(state_data.get("state", UserState.IDLE.value))
            except json.JSONDecodeError:
                return UserState.IDLE
        return UserState.IDLE

    async def set_state(self, psid: str, state: UserState, context: dict = None):
        if context is None:
            context = {}
        data = {
            "state": state.value,
            "context": context
        }
        await self.redis.set(self._get_key(psid), json.dumps(data), ex=86400) # 24 hours expiry

    async def get_context(self, psid: str) -> dict:
        data = await self.redis.get(self._get_key(psid))
        if data:
            try:
                return json.loads(data).get("context", {})
            except json.JSONDecodeError:
                return {}
        return {}

    async def update_context(self, psid: str, new_context: dict):
        state = await self.get_state(psid)
        context = await self.get_context(psid)
        context.update(new_context)
        await self.set_state(psid, state, context)

fsm = StateMachine()
