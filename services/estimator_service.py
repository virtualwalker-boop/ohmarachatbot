import os
import json
import httpx
import logging
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from core.config import settings

logger = logging.getLogger(__name__)

class CostEstimateResponse(BaseModel):
    possible_causes: list[str] = Field(description="List of 3-5 likely technical causes of the stated issue based on the brand/model/symptom (keep each brief, under 10 words)")
    low_estimate: float = Field(description="Minimum estimated parts & labor cost in PHP")
    appliance_average_price: float = Field(description="Typical retail price of this brand/model appliance (new) in the Philippines in PHP")

class DiagnosisResponse(BaseModel):
    possible_issues: list[str] = Field(description="List of 3-5 likely technical issues or causes based on appliance details and symptoms (keep each brief, under 15 words)")

class EstimatorService:
    def __init__(self):
        # Inato Electronics Shop Coordinates (origins)
        self.shop_lat = 10.366142349316457
        self.shop_lon = 123.91435245105635

    async def get_google_maps_distance_and_duration(self, destination: str) -> dict:
        """
        Calls the Google Maps Distance Matrix API to calculate the driving distance in kilometers and duration in minutes.
        Falls back to a default distance of 5.0 km and duration of 60.0 minutes if API call fails or key is missing.
        """
        api_key = settings.google_maps_api_key
        
        # Check if active API key is set
        if not api_key or api_key == "YOUR_GOOGLE_MAPS_API_KEY":
            logger.warning("Google Maps API key is not configured. Falling back to 5.0 km and 60.0 mins.")
            return {"distance_km": 5.0, "duration_mins": 60.0}
            
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{self.shop_lat},{self.shop_lon}",
            "destinations": destination,
            "key": api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK":
                        rows = data.get("rows", [])
                        if rows:
                            elements = rows[0].get("elements", [])
                            if elements:
                                element = elements[0]
                                if element.get("status") == "OK":
                                    distance_meters = element["distance"]["value"]
                                    distance_km = distance_meters / 1000.0
                                    duration_seconds = element["duration"]["value"]
                                    duration_mins = duration_seconds / 60.0
                                    logger.info(f"Google Maps calculated distance: {distance_km} km, duration: {duration_mins} mins")
                                    return {"distance_km": distance_km, "duration_mins": duration_mins}
                                else:
                                    logger.error(f"Google Maps element status error: {element.get('status')}")
                    logger.error(f"Google Maps API returned error or bad status: {data.get('status')}")
        except Exception as e:
            logger.error(f"Error calling Google Maps Distance Matrix API: {e}")
            
        logger.warning(f"Google Maps API call failed. Falling back to 5.0 km and 60.0 mins.")
        return {"distance_km": 5.0, "duration_mins": 60.0}

    async def estimate_cost(self, context: dict) -> dict:
        """
        Queries Google Gemini to dynamically calculate a realistic line-item preliminary cost estimate
        using a custom structured prompt for Inato Electronics Cebu.
        """
        service_type = context.get("service_type", "DROP_OFF")
        appliance_category = (context.get("appliance_category") or "general").lower()
        appliance = context.get("appliance") or "Appliance"
        symptom = (context.get("symptom") or "").lower()
        address = context.get("address", "")
        landmark = context.get("landmark", "")
        
        brand = context.get("brand") or "Generic"
        model = context.get("model") or "Standard"

        # Determine the admin/diagnostic fee dynamically to supply to Gemini
        admin_fee = 0.0
        distance = 0.0
        transport_cost = 0.0
        travel_hours = 0.0
        travel_cost = 0.0
        diagnostic_hours = 0.0
        diagnostic_labor = 0.0
        destination = ""

        if service_type == "HOME_SERVICE":
            # Combine address and landmark for highest Google Maps accuracy
            destination = f"{address or ''} {landmark or ''}".strip()
            maps_data = await self.get_google_maps_distance_and_duration(destination)
            distance = maps_data["distance_km"]
            duration_mins = maps_data["duration_mins"]
            
            transport_cost = (distance / 20.0) * 200.0
            
            travel_hours = duration_mins / 60.0
            travel_cost = travel_hours * 500.0
            
            if "cooling" in appliance_category or "refrigerator" in appliance_category or "ac" in appliance_category:
                diagnostic_hours = 2.0
            elif "laundry" in appliance_category or "washing" in appliance_category or "stove" in appliance_category:
                diagnostic_hours = 1.5
            else:
                diagnostic_hours = 1.0
            diagnostic_labor = diagnostic_hours * 500.0
            
            import math
            admin_fee = math.ceil((transport_cost + travel_cost + diagnostic_labor) / 50.0) * 50.0

        # Map broad categories to descriptive names for the AI estimator
        category_mapping = {
            "laundry": "Washing Machine / Dryer / Laundry Equipment",
            "cooling": "Refrigerator / Freezer / Chiller / Cooler",
            "ac": "Air Conditioner (AC)",
            "kitchen": "Stove / Oven / Gas Range",
            "small_electronics": "Small Household Appliance (e.g., Electric Fan, Rice Cooker, Microwave, Blender)"
        }
        display_category = category_mapping.get(appliance_category, appliance_category)

        # Build prompt to get structured response
        prompt = f"""Act as an expert appliance repair cost estimator based in Cebu, Philippines. Your goal is to analyze the customer's appliance issue and return the most likely technical causes and the minimum estimated parts and labor cost (in Philippine Pesos ₱), along with the typical average retail price of this appliance unit (brand/model) in the Philippines.

Here are the details of the job:
- Appliance: {appliance}
- Brand: {brand}
- Model: {model}
- Issue/Symptom: {symptom}

Please return the response as a JSON object matching the requested schema:
1. possible_causes: A list of 3 to 5 likely technical causes for the described symptoms (each cause should be under 10 words). Important: Propose only physically appropriate causes for the actual appliance type deduced from the brand, model, and symptom. Do NOT list software, firmware, RAM, internal storage, or battery issues for simple electro-mechanical devices like electric fans, washing machines, or stoves.
2. low_estimate: Minimum estimated parts and labor cost in PHP standard in Metro Cebu.
3. appliance_average_price: Typical retail price of this brand/model appliance (new) in the Philippines in PHP.
"""

        try:
            api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CostEstimateResponse,
                    temperature=0.2,
                ),
            )
            
            res_json = json.loads(response.text)
            
            repair_low = res_json.get("low_estimate", 1000.0)
            appliance_price = res_json.get("appliance_average_price", 10000.0)
            repair_high = appliance_price * 0.3
            if repair_low >= repair_high:
                repair_low = repair_high * 0.9
            possible_causes = res_json.get("possible_causes", [])
            
            causes_bullet = "\n".join([f"• {cause}" for cause in possible_causes])
            
            formatted_text = (
                f"🧾 **Preliminary Cost Estimate**\n"
                f"---------------------------------\n"
                f"🔧 **Estimated Repair Range:** ₱{repair_low:,.2f} – ₱{repair_high:,.2f}\n"
                f"🚘 **Service Mode:** {'Home Service 🏠' if service_type == 'HOME_SERVICE' else 'Drop-off 🚚'}\n\n"
            )
            
            if service_type == "HOME_SERVICE":
                formatted_text += (
                    f"⚠️ **Home Service Diagnostics Fee:** ₱{admin_fee:,.2f}\n"
                    f"*(Charged and may be collected separately at inspection)*\n\n"
                )
                
            if possible_causes:
                formatted_text += (
                    f"🔍 **Likely Technical Causes:**\n"
                    f"{causes_bullet}\n\n"
                )
                
            formatted_text += (
                f"📢 **Disclaimer:** This is a preliminary cost estimate only. "
                f"A formal, binding quotation will be provided once our technician inspects the unit in person at your location."
            )
            
            return {
                "service_type": service_type,
                "distance_km": round(distance, 2),
                "estimated_repair_labor_low": repair_low,
                "estimated_repair_labor_high": repair_high,
                "formatted_text": formatted_text,
                "diagnostics_fee_details": {
                    "transportation_cost": round(transport_cost, 2),
                    "travel_time_hours": travel_hours,
                    "travel_time_cost": round(travel_cost, 2),
                    "estimated_diagnostic_duration_hours": diagnostic_hours,
                    "diagnostic_labor_cost": round(diagnostic_labor, 2),
                    "total_diagnostics_fee": round(admin_fee, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error calling Gemini API for cost estimation: {e}")
            # Fallback to local heuristic calculations if API call fails
            possible_causes = []
            if "laundry" in appliance_category or "washing" in appliance_category:
                if "leak" in symptom:
                    repair_low = 1200.0
                    possible_causes = ["Damaged door gasket/seal", "Clogged drain hose or pump filter", "Worn tub seal or outer tub crack"]
                elif "spin" in symptom or "drum" in symptom:
                    repair_low = 1500.0
                    possible_causes = ["Worn drive belt or motor capacitor", "Defective motor or motor brushes", "Failing transmission/gearbox"]
                elif "drain" in symptom:
                    repair_low = 800.0
                    possible_causes = ["Clogged or defective drain pump", "Blocked drain hose or filter", "Loose wiring to pump connector"]
                else:
                    repair_low = 1000.0
                    possible_causes = ["General mechanical wear", "Wiring connectivity issue"]
                average_price = 15000.0
            elif "cooling" in appliance_category or "refrigerator" in appliance_category:
                repair_low = 1500.0
                possible_causes = ["Faulty thermostat or start relay", "Defective compressor or fan motor", "Refrigerant leak or blocked coils"]
                average_price = 20000.0
            elif "ac" in appliance_category or "aircon" in appliance_category:
                repair_low = 600.0
                possible_causes = ["Dirty filters or evaporator coils", "Faulty capacitor or fan motor", "Refrigerant leak or compressor failure"]
                average_price = 18000.0
            elif "stove" in appliance_category or "range" in appliance_category:
                repair_low = 800.0
                possible_causes = ["Broken igniter or heating element", "Defective thermostat or infinite switch", "Loose wiring or gas valve block"]
                average_price = 12000.0
            elif "fan" in appliance_category or "electronics" in appliance_category:
                repair_low = 300.0
                possible_causes = ["Blown thermal fuse", "Broken switch or speed dial", "Damaged power cord or connector"]
                average_price = 3000.0
            else:
                repair_low = 1000.0
                possible_causes = ["Electrical control board failure", "General component wear"]
                average_price = 10000.0

            repair_high = average_price * 0.3
            if repair_low >= repair_high:
                repair_low = repair_high * 0.9

            causes_bullet = "\n".join([f"• {cause}" for cause in possible_causes])
            
            formatted_text = (
                f"🧾 **Preliminary Cost Estimate**\n"
                f"---------------------------------\n"
                f"🔧 **Estimated Repair Range:** ₱{repair_low:,.2f} – ₱{repair_high:,.2f}\n"
                f"🚘 **Service Mode:** {'Home Service 🏠' if service_type == 'HOME_SERVICE' else 'Drop-off 🚚'}\n\n"
            )
            
            if service_type == "HOME_SERVICE":
                formatted_text += (
                    f"⚠️ **Home Service Diagnostics Fee:** ₱{admin_fee:,.2f}\n"
                    f"*(Charged and may be collected separately at inspection)*\n\n"
                )
                
            if possible_causes:
                formatted_text += (
                    f"🔍 **Likely Technical Causes:**\n"
                    f"{causes_bullet}\n\n"
                )
                
            formatted_text += (
                f"📢 **Disclaimer:** This is a preliminary cost estimate only. "
                f"A formal, binding quotation will be provided once our technician inspects the unit in person at your location."
            )

            return {
                "service_type": service_type,
                "distance_km": round(distance, 2),
                "estimated_repair_labor_low": repair_low,
                "estimated_repair_labor_high": repair_high,
                "formatted_text": formatted_text,
                "diagnostics_fee_details": {
                    "transportation_cost": round(transport_cost, 2),
                    "travel_time_hours": travel_hours,
                    "travel_time_cost": round(travel_cost, 2),
                    "estimated_diagnostic_duration_hours": diagnostic_hours,
                    "diagnostic_labor_cost": round(diagnostic_labor, 2),
                    "total_diagnostics_fee": round(admin_fee, 2)
                }
            }

    async def diagnose_issues(self, appliance_details: str, issue: str) -> list[str]:
        """
        Calls Google Gemini to diagnose possible technical issues/causes
        based on the appliance details (name/brand/model) and the customer's description of the issue.
        """
        prompt = f"""Act as an expert appliance repair technician. Your task is to diagnose the customer's appliance issue based on the appliance details and symptom description. Propose 3 to 5 most likely technical causes.
        
Here are the details:
- Appliance Details (Name/Brand/Model): {appliance_details}
- Described Issue/Symptom: {issue}

Please return the response as a JSON object matching the requested schema:
- possible_issues: A list of 3 to 5 likely technical issues or causes (each under 15 words). Important: Propose only physically appropriate causes for the actual appliance type. Do NOT list software, firmware, RAM, internal storage, or battery issues for simple electro-mechanical devices like electric fans, washing machines, or stoves.
"""
        try:
            api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DiagnosisResponse,
                    temperature=0.2,
                ),
            )
            
            res_json = json.loads(response.text)
            return res_json.get("possible_issues", [])
        except Exception as e:
            logger.error(f"Error calling Gemini API for diagnosis: {e}")
            # Simple local fallback heuristic
            issues = []
            desc_lower = issue.lower()
            details_lower = appliance_details.lower()
            if "washing" in details_lower or "washer" in details_lower or "laundry" in details_lower:
                if "leak" in desc_lower:
                    issues = ["Damaged door gasket/seal", "Clogged drain hose or pump filter", "Worn tub seal or outer tub crack"]
                elif "spin" in desc_lower or "drum" in desc_lower:
                    issues = ["Worn drive belt or motor capacitor", "Defective motor or motor brushes", "Failing transmission/gearbox"]
                else:
                    issues = ["Defective drain pump", "General mechanical wear or loose wiring"]
            elif "fridge" in details_lower or "refrigerator" in details_lower or "cooling" in details_lower:
                issues = ["Faulty thermostat or start relay", "Defective compressor or fan motor", "Refrigerant leak or blocked coils"]
            elif "ac" in details_lower or "aircon" in details_lower or "air" in details_lower:
                issues = ["Dirty filters or evaporator coils", "Faulty capacitor or fan motor", "Refrigerant leak or compressor failure"]
            else:
                issues = ["Electrical control board failure", "General component wear", "Blown thermal fuse or power supply fault"]
            return issues

estimator_service = EstimatorService()
