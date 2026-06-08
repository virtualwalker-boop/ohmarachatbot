import pytest
import json
from services.estimator_service import estimator_service

@pytest.fixture
def mock_gemini_diagnose(monkeypatch):
    class MockModels:
        def generate_content(self, model, contents, config=None):
            class MockResponse:
                def __init__(self, text_val):
                    self.text = text_val
            
            res = {
                "possible_issues": [
                    "Defective heating element",
                    "Faulty high limit thermostat",
                    "Broken thermal fuse"
                ]
            }
            return MockResponse(json.dumps(res))

    class MockClient:
        def __init__(self, api_key=None):
            self.models = MockModels()

    from google import genai
    monkeypatch.setattr(genai, "Client", MockClient)

@pytest.mark.asyncio
async def test_diagnose_issues_success(mock_gemini_diagnose):
    issues = await estimator_service.diagnose_issues(
        appliance_details="Samsung Model Dryer",
        issue="not drying clothes"
    )
    assert len(issues) == 3
    assert "Defective heating element" in issues
    assert "Faulty high limit thermostat" in issues

@pytest.mark.asyncio
async def test_diagnose_issues_fallback_laundry(monkeypatch):
    # Force Client construction to raise exception to trigger fallback
    def mock_client_error(*args, **kwargs):
        raise Exception("API Key Error or Network Timeout")
        
    from google import genai
    monkeypatch.setattr(genai, "Client", mock_client_error)
    
    # Test laundry fallback (leak)
    issues = await estimator_service.diagnose_issues(
        appliance_details="Samsung Washing Machine",
        issue="water is leaking"
    )
    assert "Damaged door gasket/seal" in issues
    assert "Clogged drain hose or pump filter" in issues
    
    # Test laundry fallback (spin)
    issues = await estimator_service.diagnose_issues(
        appliance_details="Panasonic Washer",
        issue="drum not spinning"
    )
    assert "Worn drive belt or motor capacitor" in issues

@pytest.mark.asyncio
async def test_diagnose_issues_fallback_cooling(monkeypatch):
    def mock_client_error(*args, **kwargs):
        raise Exception("API Key Error or Network Timeout")
        
    from google import genai
    monkeypatch.setattr(genai, "Client", mock_client_error)
    
    # Test cooling fallback
    issues = await estimator_service.diagnose_issues(
        appliance_details="Panasonic Refrigerator",
        issue="fridge not cooling"
    )
    assert "Faulty thermostat or start relay" in issues
    assert "Defective compressor or fan motor" in issues
