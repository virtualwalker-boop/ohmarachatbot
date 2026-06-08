import pytest
from core.config import settings
import hmac
import hashlib
import json

@pytest.mark.asyncio
async def test_verify_webhook(async_client):
    response = await async_client.get(
        f"/api/v1/messenger/webhook?hub_mode=subscribe&hub_verify_token={settings.meta_verify_token}&hub_challenge=1158201444"
    )
    assert response.status_code == 200
    assert response.text == "1158201444"

@pytest.mark.asyncio
async def test_verify_webhook_invalid_token(async_client):
    response = await async_client.get(
        "/api/v1/messenger/webhook?hub_mode=subscribe&hub_verify_token=wrong_token&hub_challenge=1158201444"
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_receive_webhook_valid(async_client, mock_redis):
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "123456"},
                        "message": {"text": "I need help with my booking"}
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    response = await async_client.post(
        "/api/v1/messenger/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 200
    assert response.json() == "EVENT_RECEIVED"

@pytest.mark.asyncio
async def test_confirm_booking_quick_reply(async_client, mock_redis, monkeypatch):
    from api.v1 import messenger
    
    sent_payloads = []
    async def mock_send_messenger_response(psid, payload):
        sent_payloads.append(payload)
        
    monkeypatch.setattr(messenger, "send_messenger_response", mock_send_messenger_response)
    
    from core.state import fsm, UserState
    await fsm.set_state("123456", UserState.QUOTATION_GENERATED, {"name": "Test User", "service_type": "DROP_OFF"})
    
    # Send CONFIRM_BOOKING postback via webhook
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "123456"},
                        "postback": {"payload": "CONFIRM_BOOKING"}
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    response = await async_client.post(
        "/api/v1/messenger/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 200
    assert response.json() == "EVENT_RECEIVED"
    
    # Check that we sent a response with the BACK_TO_MAIN_MENU quick reply
    assert len(sent_payloads) == 1
    assert "quick_replies" in sent_payloads[0]
    assert sent_payloads[0]["quick_replies"][0]["payload"] == "BACK_TO_MAIN_MENU"
    
    # Now simulate user clicking "Back to Main Menu" (sends quick reply payload)
    sent_payloads.clear()
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "123456"},
                        "message": {
                            "text": "Back to Main Menu",
                            "quick_reply": {"payload": "BACK_TO_MAIN_MENU"}
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    response = await async_client.post(
        "/api/v1/messenger/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 200
    assert response.json() == "EVENT_RECEIVED"
    
    # Check that the main menu carousel is sent
    assert len(sent_payloads) == 1
    assert "attachment" in sent_payloads[0]
    assert sent_payloads[0]["attachment"]["type"] == "template"
    assert sent_payloads[0]["attachment"]["payload"]["template_type"] == "generic"


@pytest.mark.asyncio
async def test_track_bookings_carousel_quick_reply(async_client, mock_redis, monkeypatch):
    from api.v1 import messenger
    from services.tracker_service import tracker_service
    
    # Mock active bookings
    class MockBooking:
        def __init__(self, id, service_type, brand, model, appliance_category, status):
            self.id = id
            self.service_type = service_type
            self.brand = brand
            self.model = model
            self.appliance_category = appliance_category
            self.status = status
            
    async def mock_get_active_orders_by_psid(db, psid):
        return [
            MockBooking(1, "HOME_SERVICE", "Electrolux", "top load", "laundry", "PENDING")
        ]
        
    monkeypatch.setattr(tracker_service, "get_active_orders_by_psid", mock_get_active_orders_by_psid)
    
    sent_payloads = []
    async def mock_send_messenger_response(psid, payload):
        sent_payloads.append(payload)
        
    monkeypatch.setattr(messenger, "send_messenger_response", mock_send_messenger_response)
    
    from core.state import fsm, UserState
    await fsm.set_state("123456", UserState.IDLE, {"nlp_failures": 0})
    
    # Send TRACK_BOOKINGS postback via webhook
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "123456"},
                        "postback": {"payload": "TRACK_BOOKINGS"}
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    response = await async_client.post(
        "/api/v1/messenger/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 200
    assert response.json() == "EVENT_RECEIVED"
    
    # Check that we sent 2 messages (one text prompt and one generic template/carousel)
    # The first message: "🔍 **Your Active Service Requests:**"
    # The second message: generic template with quick replies
    assert len(sent_payloads) == 2
    assert sent_payloads[0] == {"text": "🔍 **Your Active Service Requests:**"}
    assert "attachment" in sent_payloads[1]
    
    # Assert on carousel button
    carousel_payload = sent_payloads[1]["attachment"]["payload"]
    assert len(carousel_payload["elements"]) == 1
    element = carousel_payload["elements"][0]
    assert element["buttons"][0]["title"] == "View Details"
    assert element["buttons"][0]["payload"] == "VIEW_DETAILS_1"

    # Assert on quick replies
    assert "quick_replies" in sent_payloads[1]
    assert len(sent_payloads[1]["quick_replies"]) == 2
    assert sent_payloads[1]["quick_replies"][0]["title"] == "Track my Bookings"
    assert sent_payloads[1]["quick_replies"][0]["payload"] == "TRACK_BOOKINGS"
    assert sent_payloads[1]["quick_replies"][1]["title"] == "Main Menu"
    assert sent_payloads[1]["quick_replies"][1]["payload"] == "BACK_TO_MAIN_MENU"


@pytest.mark.asyncio
async def test_view_booking_details(async_client, mock_redis, monkeypatch):
    from api.v1 import messenger
    
    # Mock database session and query result
    class MockQuotation:
        total_amount = 850.0
        pdf_url = "http://example.com/quotation.pdf"
        
    class MockBooking:
        id = 999
        status = "PENDING"
        service_type = "HOME_SERVICE"
        brand = "Electrolux"
        model = "top load"
        appliance_category = "laundry"
        symptom = "leaking water"
        address = "Talamban Cebu"
        landmark = "Gym"
        estimated_cost_json = None
        quotation = MockQuotation()
        
    class MockAsyncSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def execute(self, stmt):
            class MockResult:
                def scalars(self):
                    class MockScalars:
                        def first(self):
                            return MockBooking()
                    return MockScalars()
            return MockResult()
            
    monkeypatch.setattr(messenger, "AsyncSessionLocal", MockAsyncSession)

    sent_payloads = []
    async def mock_send_messenger_response(psid, payload):
        sent_payloads.append(payload)
        
    monkeypatch.setattr(messenger, "send_messenger_response", mock_send_messenger_response)
    
    from core.state import fsm, UserState
    await fsm.set_state("123456", UserState.IDLE, {"nlp_failures": 0})
    
    # Send VIEW_DETAILS postback via webhook
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "123456"},
                        "postback": {"payload": "VIEW_DETAILS_999"}
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    response = await async_client.post(
        "/api/v1/messenger/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 200
    assert response.json() == "EVENT_RECEIVED"
    
    # Verify that the booking details were sent
    assert len(sent_payloads) == 1
    details = sent_payloads[0]
    assert "Booking Details" in details["text"]
    assert "#INATO-B999" in details["text"]
    assert "Electrolux" in details["text"]
    assert "leaking water" in details["text"]
    assert "₱850.00" in details["text"]
    
    # Verify the quick replies
    assert len(details["quick_replies"]) == 2
    assert details["quick_replies"][0]["title"] == "Track my Bookings"
    assert details["quick_replies"][0]["payload"] == "TRACK_BOOKINGS"
    assert details["quick_replies"][1]["title"] == "Main Menu"
    assert details["quick_replies"][1]["payload"] == "BACK_TO_MAIN_MENU"


