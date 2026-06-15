import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
import core.state

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture
async def mock_redis(monkeypatch):
    data_store = {}

    class MockCustomer:
        def __init__(self, fb_psid):
            self.fb_psid = fb_psid
            self.fsm_state = "IDLE"
            self.fsm_context = {}

    class MockDBSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def execute(self, stmt):
            try:
                params = stmt.compile().params
                psid = list(params.values())[0]
            except Exception:
                psid = "default"

            if psid not in data_store:
                data_store[psid] = MockCustomer(psid)

            customer = data_store[psid]

            class MockResult:
                def scalars(self):
                    class MockScalars:
                        def first(self):
                            return customer
                    return MockScalars()
            return MockResult()

        def add(self, obj):
            data_store[obj.fb_psid] = obj

        async def commit(self):
            pass

    monkeypatch.setattr(core.state, "AsyncSessionLocal", MockDBSession)
    return data_store
