import pytest
from services.faq_service import faq_service

def test_faq_service_load():
    # Verify that the sections have been loaded and parsed correctly from the actual knowledgebase.md
    assert len(faq_service.sections) > 1
    assert "BUSINESS PROFILE & CORE IDENTITY" in faq_service.sections
    assert "CONTACT AND LOCATION METADATA" in faq_service.sections
    assert "TECHNICAL REPAIR DOMAIN 1: LAUNDRY SHOP EQUIPMENT & WASHING MACHINES" in faq_service.sections

def test_faq_service_location_query():
    query = "Where are you located?"
    response = faq_service.get_answer(query)
    assert "Hi-way 77, Talamban, Cebu City" in response
    assert "+63 927 154 0088" in response

def test_faq_service_laundry_query():
    query = "My washing machine is leaking"
    response = faq_service.get_answer(query)
    assert "Leaking Washer" in response
    assert "door bellows gaskets" in response

def test_faq_service_refrigerator_query():
    query = "My fridge is not cooling"
    response = faq_service.get_answer(query)
    assert "Refrigerator / Chiller Not Cooling" in response
    assert "defrost system diagnostics" in response

def test_faq_service_stove_query():
    query = "Stove burner is not igniting"
    response = faq_service.get_answer(query)
    assert "Kitchen Appliance Repairs" in response
    assert "clogged burner orifices" in response

def test_faq_service_fan_query():
    query = "Electric fan is not spinning"
    response = faq_service.get_answer(query)
    assert "Electric Fan Servicing" in response
    assert "motor run capacitors" in response

def test_faq_service_privacy_query():
    query = "What is your data privacy policy?"
    response = faq_service.get_answer(query)
    assert "Republic Act No. 10173" in response

def test_faq_service_booking_query():
    query = "How can I book a service?"
    response = faq_service.get_answer(query)
    assert "How to Book a Repair Service" in response
