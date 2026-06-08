import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from core.state import fsm, UserState
import json

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture
async def mock_redis(monkeypatch):
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        async def get(self, key):
            return self.data.get(key)
            
        async def set(self, key, value, ex=None):
            self.data[key] = value

    mock_db = MockRedis()
    monkeypatch.setattr(fsm, "redis", mock_db)
    return mock_db
