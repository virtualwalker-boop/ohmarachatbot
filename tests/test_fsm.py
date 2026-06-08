import pytest
from core.state import fsm, UserState
import json

@pytest.mark.asyncio
async def test_fsm_initial_state(mock_redis):
    state = await fsm.get_state("user_123")
    assert state == UserState.IDLE

@pytest.mark.asyncio
async def test_fsm_state_transition(mock_redis):
    await fsm.set_state("user_123", UserState.FAQ_LOOP)
    state = await fsm.get_state("user_123")
    assert state == UserState.FAQ_LOOP

@pytest.mark.asyncio
async def test_fsm_context_update(mock_redis):
    await fsm.set_state("user_123", UserState.IDLE, {"visits": 1})
    await fsm.update_context("user_123", {"name": "John"})
    
    context = await fsm.get_context("user_123")
    assert context == {"visits": 1, "name": "John"}
