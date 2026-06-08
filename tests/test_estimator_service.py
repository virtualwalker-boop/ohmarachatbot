import pytest
import json
from services.estimator_service import estimator_service

@pytest.fixture(autouse=True)
def mock_gemini_client(monkeypatch):
    class MockModels:
        def generate_content(self, model, contents, config=None):
            low = 1000.0
            high = 3000.0
            causes = ["Mock cause 1", "Mock cause 2"]
            
            contents_lower = contents.lower()
            # Match prompt inputs to return the expected test values by checking the specific appliance line
            if any(x in contents_lower for x in ["appliance: washing", "appliance: washer", "appliance: laundry"]):
                if "leak" in contents_lower:
                    low = 1200.0
                    high = 2500.0
                    causes = ["Damaged door gasket/seal", "Clogged drain hose or pump filter", "Worn tub seal or outer tub crack"]
                elif "spin" in contents_lower or "drum" in contents_lower:
                    low = 1500.0
                    high = 3500.0
                    causes = ["Worn drive belt or motor capacitor", "Defective motor or motor brushes", "Failing transmission/gearbox"]
            elif any(x in contents_lower for x in ["appliance: cooling", "appliance: refrigerator", "appliance: fridge"]):
                low = 1500.0
                high = 4000.0
                causes = ["Faulty thermostat or start relay", "Defective compressor or fan motor"]

            class MockResponse:
                def __init__(self, text_val):
                    self.text = text_val
                    
            res = {
                "possible_causes": causes,
                "low_estimate": low,
                "appliance_average_price": 15000.0
            }
            return MockResponse(json.dumps(res))

    class MockClient:
        def __init__(self, api_key=None):
            self.models = MockModels()

    from google import genai
    monkeypatch.setattr(genai, "Client", MockClient)

@pytest.mark.asyncio
async def test_estimate_cost_drop_off():
    context = {
        "service_type": "DROP_OFF",
        "appliance_category": "laundry",
        "appliance": "Washing Machine",
        "symptom": "water leaking from the door",
        "address": "",
        "landmark": ""
    }
    est = await estimator_service.estimate_cost(context)
    
    assert est["service_type"] == "DROP_OFF"
    assert est["distance_km"] == 0.0
    assert est["estimated_repair_labor_low"] == 1200.0
    assert est["estimated_repair_labor_high"] == 4500.0
    
    details = est["diagnostics_fee_details"]
    assert details["transportation_cost"] == 0.0
    assert details["travel_time_hours"] == 0.0
    assert details["travel_time_cost"] == 0.0
    assert details["estimated_diagnostic_duration_hours"] == 0.0
    assert details["diagnostic_labor_cost"] == 0.0
    assert details["total_diagnostics_fee"] == 0.0

@pytest.mark.asyncio
async def test_estimate_cost_home_service_mocked_google_maps(monkeypatch):
    # Mock get_google_maps_distance_and_duration to simulate a 0.5 km and 30 min Google Maps routing result
    async def mock_get_distance_and_duration(self, destination: str) -> dict:
        if "Talamban Gym" in destination:
            return {"distance_km": 0.5, "duration_mins": 30.0}
        return {"distance_km": 5.23, "duration_mins": 45.0}
        
    monkeypatch.setattr(estimator_service.__class__, "get_google_maps_distance_and_duration", mock_get_distance_and_duration)

    context = {
        "service_type": "HOME_SERVICE",
        "appliance_category": "laundry",
        "appliance": "Washing Machine",
        "symptom": "washing machine fails to spin",
        "address": "Talamban Gym area",
        "landmark": "Talamban Gym"
    }
    est = await estimator_service.estimate_cost(context)
    
    assert est["service_type"] == "HOME_SERVICE"
    assert est["estimated_repair_labor_low"] == 1500.0
    assert est["estimated_repair_labor_high"] == 4500.0
    assert est["distance_km"] == 0.5
    
    details = est["diagnostics_fee_details"]
    # 0.5 km transport: (0.5 / 20.0) * 200.0 = ₱5.00
    assert details["transportation_cost"] == 5.0
    
    # 30 mins -> 0.5 travel hours
    assert details["travel_time_hours"] == 0.5
    # Travel Time Cost: 0.5 * 500.0 = ₱250.00
    assert details["travel_time_cost"] == 250.0
    
    # Laundry diagnostics labor: 1.5 hours
    assert details["estimated_diagnostic_duration_hours"] == 1.5
    # Diagnostics labor cost: 1.5 * 500 = ₱750.00
    assert details["diagnostic_labor_cost"] == 750.0
    
    # Total Diagnostics Fee: 5.0 (transport) + 250.0 (travel) + 750.0 (labor) = ₱1005.00, rounded up to multiple of ₱50 -> ₱1050.00
    assert details["total_diagnostics_fee"] == 1050.0

@pytest.mark.asyncio
async def test_estimate_cost_home_service_fallback_mode():
    # If no mock is set, it will detect unconfigured API key and fallback to 5.0 km
    context = {
        "service_type": "HOME_SERVICE",
        "appliance_category": "cooling",
        "appliance": "Refrigerator",
        "symptom": "fridge is not cooling",
        "address": "Unknown location",
        "landmark": "No landmark"
    }
    est = await estimator_service.estimate_cost(context)
    
    assert est["service_type"] == "HOME_SERVICE"
    assert est["distance_km"] == 5.0  # Fallback
    assert est["estimated_repair_labor_low"] == 1500.0
    assert est["estimated_repair_labor_high"] == 4500.0
    
    details = est["diagnostics_fee_details"]
    # 5.0 km transport: (5.0 / 20.0) * 200.0 = ₱50.00
    assert details["transportation_cost"] == 50.0
    
    # Distance <= 10 km -> 1.0 travel hours
    assert details["travel_time_hours"] == 1.0
    assert details["travel_time_cost"] == 500.0
    
    # Refrigerator diagnostics labor: 2.0 hours
    assert details["estimated_diagnostic_duration_hours"] == 2.0
    # Diagnostics labor cost: 2.0 * 500 = ₱1000.00
    assert details["diagnostic_labor_cost"] == 1000.0
    
    # Total Diagnostics Fee: 50.0 + 500.0 + 1000.0 = ₱1550.00
    assert details["total_diagnostics_fee"] == 1550.0
