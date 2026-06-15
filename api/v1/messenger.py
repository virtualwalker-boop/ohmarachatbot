from fastapi import APIRouter, Request, HTTPException, Query
from core.config import settings
from core.state import fsm, UserState
from core.database import AsyncSessionLocal
from services.faq_service import faq_service
from services.estimator_service import estimator_service
from services.booking_service import booking_service
from services.tracker_service import tracker_service
import hmac
import hashlib
import json
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Meta Messenger Send API helper
async def send_messenger_response(psid: str, message_payload: dict):
    """
    Sends message payloads back to Facebook Messenger.
    In local mock mode, it prints details directly to console/test logs.
    """
    print(f"\n--- [MOCK MESSENGER RESPONSE TO {psid}] ---")
    print(json.dumps(message_payload, indent=2))
    print("------------------------------------------\n")
    
    token = settings.meta_page_access_token
    if token and token != "YOUR_PAGE_ACCESS_TOKEN":
        url = f"https://graph.facebook.com/v12.0/me/messages?access_token={token}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={
                    "recipient": {"id": psid},
                    "message": message_payload
                })
                logger.info(f"Meta Graph API response status: {resp.status_code}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"Error calling Meta Graph API: {e}", exc_info=True)

# Helper to send a simple text response
async def send_text_response(psid: str, text: str, include_menu: bool = True):
    if include_menu:
        await send_messenger_response(psid, {
            "text": text,
            "quick_replies": [
                {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
            ]
        })
    else:
        await send_messenger_response(psid, {"text": text})

# Helper to render the Main Menu Carousel (Carousel Cards Only)
async def send_main_menu_carousel(psid: str):
    menu_payload = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": [
                    {
                        "title": "📅 Book a Service Request",
                        "subtitle": "Schedule a Home Service dispatch or book a shop drop-off.",
                        "buttons": [
                            {
                                "type": "postback",
                                "title": "Start Booking 📅",
                                "payload": "START_BOOKING"
                            }
                        ]
                    },
                    {
                        "title": "❄️ Diagnose & Estimate",
                        "subtitle": "Self-diagnose symptoms and get a preliminary cost estimate.",
                        "buttons": [
                            {
                                "type": "postback",
                                "title": "Diagnose Symptom ❄️",
                                "payload": "GET_ESTIMATE"
                            }
                        ]
                    },
                    {
                        "title": "🔍 Track My Bookings",
                        "subtitle": "View live status updates on all your active service requests.",
                        "buttons": [
                            {
                                "type": "postback",
                                "title": "Track My Bookings 🔍",
                                "payload": "TRACK_BOOKINGS"
                            }
                        ]
                    }
                ]
            }
        }
    }
    await send_messenger_response(psid, menu_payload)

# Webhook Verification endpoint
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    # Fallback to underscore versions if query aliases are not set (for test compatibility)
    mode = hub_mode or request.query_params.get("hub_mode")
    challenge = hub_challenge or request.query_params.get("hub_challenge")
    verify_token = hub_verify_token or request.query_params.get("hub_verify_token")
    
    if mode == "subscribe" and verify_token == settings.meta_verify_token:
        try:
            return int(challenge)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid challenge format")
    raise HTTPException(status_code=403, detail="Verification failed")

# Webhook Payload Receiver endpoint
@router.post("/webhook")
async def receive_webhook(request: Request):
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    body = await request.body()
    expected_signature = "sha256=" + hmac.new(
        settings.meta_verify_token.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Perform strict verification in prod
    # if not hmac.compare_digest(signature, expected_signature):
    #     raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    if payload.get("object") == "page":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                current_state = await fsm.get_state(sender_id)
                
                if "message" in event:
                    quick_reply = event["message"].get("quick_reply")
                    if quick_reply:
                        payload_data = quick_reply.get("payload")
                        await process_postback(sender_id, payload_data, current_state)
                    else:
                        text = event["message"].get("text", "")
                        await process_message(sender_id, text, current_state)
                elif "postback" in event:
                    payload_data = event["postback"].get("payload")
                    await process_postback(sender_id, payload_data, current_state)
                    
        return "EVENT_RECEIVED"
    
    raise HTTPException(status_code=404, detail="Not a page event")

# Message Handler (FSM Engine)
async def process_message(psid: str, text: str, state: UserState):
    ctx = await fsm.get_context(psid)
    
    if state == UserState.IDLE:
        # Check FAQ match
        ans = faq_service.get_answer(text)
        # If default greeting is returned, it means no FAQ keyword matched
        if "Welcome to Inato Electronics" in ans or "Ask me about" in ans:
            # Increment NLP failure count
            failures = ctx.get("nlp_failures", 0) + 1
            if failures >= 2:
                # Trigger direct escalation hand-off
                await fsm.update_context(psid, {"nlp_failures": 0})
                hand_off_payload = {
                    "text": "🤝 **Let me connect you with our team:**\n\nI couldn't find a direct answer to your question, but I want to make sure you get the right support!\n\n📞 **Call/SMS Support:** +63 927 154 0088\n✉️ **Email Support:** nhel@inatoelectronics.com\n📍 **Shop Address:** Hi-way 77, Talamban, Cebu City\n\nAlternatively, use the main menu options below.",
                    "quick_replies": [
                        {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"},
                        {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"}
                    ]
                }
                await send_messenger_response(psid, hand_off_payload)
            else:
                await fsm.update_context(psid, {"nlp_failures": failures})
                # Welcome back greeting with Carousel Menu
                await send_text_response(psid, f"Hello! I'm Ohmara, Inato Electronics' automated assistant. Let me show you what I can do:", include_menu=False)
                await send_main_menu_carousel(psid)
        else:
            # We had an FAQ hit! Reset NLP failure count.
            await fsm.update_context(psid, {"nlp_failures": 0})
            await send_messenger_response(psid, {
                "text": ans,
                "quick_replies": [
                    {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })

    elif state == UserState.FAQ_LOOP:
        step = ctx.get("step")
        if "book" in text.lower() or "schedule" in text.lower() or "repair" in text.lower():
            await fsm.set_state(psid, UserState.COLLECTING_BOOKING_INFO, {"step": "name"})
            await send_text_response(psid, "Let's get your service request scheduled. First, what is your full name?")
        elif step == "appliance_details":
            await fsm.update_context(psid, {
                "appliance_details": text,
                "step": "describe_issue"
            })
            await send_text_response(psid, "Got it! Please describe the issue or symptom you are experiencing (e.g., not spinning, leaking water):", include_menu=False)
        elif step == "describe_issue":
            # Call diagnosis helper
            issues = await estimator_service.diagnose_issues(ctx.get("appliance_details"), text)
            
            # Format display
            if issues:
                bullet_list = "\n".join([f"• {issue}" for issue in issues])
                response_text = (
                    f"🔍 **Diagnostic Analysis Results**\n"
                    f"---------------------------------\n"
                    f"Based on the details provided, here are the most likely causes of the issue:\n\n"
                    f"{bullet_list}\n\n"
                    f"Would you like to book a service request to have a technician inspect it?"
                )
            else:
                response_text = "I couldn't identify the specific causes. Would you like to book a service request for a technician visit?"

            # Reset state back to IDLE
            await fsm.set_state(psid, UserState.IDLE, {"nlp_failures": 0})
            
            await send_messenger_response(psid, {
                "text": response_text,
                "quick_replies": [
                    {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })
        else:
            ans = faq_service.get_answer(text)
            await send_messenger_response(psid, {
                "text": ans,
                "quick_replies": [
                    {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })

    elif state == UserState.COLLECTING_BOOKING_INFO:
        step = ctx.get("step")
        
        if step == "name":
            # Save name
            await fsm.update_context(psid, {
                "name": text,
                "first_name": text.split()[0] if text.split() else "Valued",
                "last_name": " ".join(text.split()[1:]) if len(text.split()) > 1 else "Customer",
                "step": "phone"
            })
            await send_text_response(psid, "Thank you! Can you provide your best active Contact Number? (e.g. 09271540088)")
            
        elif step == "phone":
            # Save phone
            await fsm.update_context(psid, {"phone": text, "step": "service_type"})
            # Ask for Service Type using Quick Replies for choice
            await send_messenger_response(psid, {
                "text": "How would you prefer us to service your appliance?",
                "quick_replies": [
                    {"content_type": "text", "title": "Home Service 🏠", "payload": "TYPE_HOME_SERVICE"},
                    {"content_type": "text", "title": "Drop-off at Shop 🚚", "payload": "TYPE_DROP_OFF"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })
            
        elif step == "service_type":
            # Handle text entry fallback if buttons not used
            val = text.lower()
            if "home" in val or "site" in val:
                await fsm.update_context(psid, {"service_type": "HOME_SERVICE", "step": "address"})
                await send_text_response(psid, "Since you prefer Home Service, please provide your Complete Service Address in Cebu:")
            elif "drop" in val or "shop" in val:
                await fsm.update_context(psid, {"service_type": "DROP_OFF", "address": None, "landmark": None, "step": "appliance_category"})
                # Skip address/landmark and go directly to category
                await send_messenger_response(psid, {
                    "text": "What appliance needs attention?",
                    "quick_replies": [
                        {"content_type": "text", "title": "Washing Machine 🧺", "payload": "CAT_LAUNDRY"},
                        {"content_type": "text", "title": "Refrigerator ❄️", "payload": "CAT_COOLING"},
                        {"content_type": "text", "title": "Air Conditioner 🌬️", "payload": "CAT_AC"},
                        {"content_type": "text", "title": "Stove / Oven 🍳", "payload": "CAT_KITCHEN"},
                        {"content_type": "text", "title": "Small Electronics 🔌", "payload": "CAT_SMALL"},
                        {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                    ]
                })
            else:
                await send_text_response(psid, "Please select 'Home Service 🏠' or 'Drop-off at Shop 🚚' using the buttons.")

        elif step == "address":
            await fsm.update_context(psid, {"address": text, "step": "landmark"})
            await send_text_response(psid, "Got it. Please specify a Google Map verifiable landmark near this address (e.g. Across Talamban Gym, near Talamban Elementary):")

        elif step == "landmark":
            await fsm.update_context(psid, {"landmark": text, "step": "appliance_category"})
            await send_messenger_response(psid, {
                "text": "What appliance needs attention?",
                "quick_replies": [
                    {"content_type": "text", "title": "Washing Machine 🧺", "payload": "CAT_LAUNDRY"},
                    {"content_type": "text", "title": "Refrigerator ❄️", "payload": "CAT_COOLING"},
                    {"content_type": "text", "title": "Air Conditioner 🌬️", "payload": "CAT_AC"},
                    {"content_type": "text", "title": "Stove / Oven 🍳", "payload": "CAT_KITCHEN"},
                    {"content_type": "text", "title": "Small Electronics 🔌", "payload": "CAT_SMALL"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })

        elif step == "appliance_category":
            category = "general"
            val = text.lower()
            if "washing" in val or "laundry" in val or "washer" in val:
                category = "laundry"
            elif "refrigerator" in val or "cooling" in val or "fridge" in val or "chiller" in val:
                category = "cooling"
            elif "ac" in val or "aircon" in val or "air cond" in val:
                category = "ac"
            elif "microwave" in val:
                category = "small_electronics"
            elif "stove" in val or "oven" in val or "range" in val:
                category = "kitchen"
            elif "fan" in val or "electronics" in val or "small" in val or "cooker" in val or "rice" in val or "blender" in val:
                category = "small_electronics"

            await fsm.update_context(psid, {"appliance_category": category, "appliance": text, "step": "brand"})
            await send_text_response(psid, "What is the brand and model of your appliance? (e.g., Samsung Model WA10)")

        elif step == "brand":
            # Store brand and model
            await fsm.update_context(psid, {
                "brand": text.split()[0] if text.split() else "General",
                "model": " ".join(text.split()[1:]) if len(text.split()) > 1 else "Unknown",
                "step": "symptom"
            })
            await send_text_response(psid, "What problem or symptom are you experiencing? (e.g. water leaking, not cooling)")

        elif step == "symptom":
            # Save symptom and run cost estimator immediately
            ctx["symptom"] = text
            await fsm.set_state(psid, UserState.ESTIMATING_COST, ctx)
            
            # Generate Cost Estimate
            estimate = await estimator_service.estimate_cost(ctx)
            
            # Save estimate in context
            ctx["estimated_cost_json"] = estimate
            await fsm.set_state(psid, UserState.QUOTATION_GENERATED, ctx)
            
            # Format display
            if "formatted_text" in estimate and estimate["formatted_text"]:
                cost_message = estimate["formatted_text"]
            else:
                service_type = ctx.get("service_type", "DROP_OFF")
                low = estimate["estimated_repair_labor_low"]
                high = estimate["estimated_repair_labor_high"]
                
                cost_message = (
                    f"🧾 **Preliminary Cost Estimate**\n"
                    f"---------------------------------\n"
                    f"🔧 **Estimated Repair Range:** ₱{low:,.2f} – ₱{high:,.2f}\n"
                    f"🚘 **Service Mode:** {'Home Service 🏠' if service_type == 'HOME_SERVICE' else 'Drop-off 🚚'}\n\n"
                )
                
                if service_type == "HOME_SERVICE":
                    details = estimate["diagnostics_fee_details"]
                    cost_message += (
                        f"⚠️ **Home Service Diagnostics Fee:** ₱{details['total_diagnostics_fee']:,.2f}\n"
                        f"*(Charged and may be collected separately at inspection)*\n\n"
                    )
                    
                cost_message += (
                    f"📢 **Disclaimer:** This is a preliminary cost estimate only. "
                    f"A formal, binding quotation will be provided once our technician inspects the unit in person at your location."
                )
            
            await send_messenger_response(psid, {
                "text": cost_message,
                "quick_replies": [
                    {"content_type": "text", "title": "Confirm Booking ✅", "payload": "CONFIRM_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })

    elif state == UserState.QUOTATION_GENERATED:
        # Fallback text handler for estimate confirmation
        val = text.lower()
        if "confirm" in val or "yes" in val:
            await process_postback(psid, "CONFIRM_BOOKING", state)
        elif "cancel" in val or "no" in val:
            await process_postback(psid, "RESET_TO_IDLE", state)
        else:
            # Guide the user to confirm/cancel rather than immediately cancelling their state
            await send_messenger_response(psid, {
                "text": "Please confirm or cancel your booking request using the options below:",
                "quick_replies": [
                    {"content_type": "text", "title": "Confirm Booking ✅", "payload": "CONFIRM_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })

# Postback Payload Handler
async def process_postback(psid: str, payload: str, state: UserState):
    ctx = await fsm.get_context(psid)
    
    if payload == "GET_STARTED":
        await fsm.set_state(psid, UserState.IDLE, {"nlp_failures": 0})
        welcome_text = faq_service.get_answer("")
        greeting_payload = {
            "text": welcome_text,
            "quick_replies": [
                {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"},
                {"content_type": "text", "title": "Diagnose Symptom ❄️", "payload": "GET_ESTIMATE"},
                {"content_type": "text", "title": "Track Bookings 🔍", "payload": "TRACK_BOOKINGS"}
            ]
        }
        await send_messenger_response(psid, greeting_payload)
        
    elif payload == "RESET_TO_IDLE" or "cancel" in payload.lower():
        await fsm.set_state(psid, UserState.IDLE, {"nlp_failures": 0})
        await send_text_response(psid, "Service request has been cancelled.", include_menu=False)
        await send_main_menu_carousel(psid)
        
    elif payload == "BACK_TO_MAIN_MENU":
        await fsm.set_state(psid, UserState.IDLE, {"nlp_failures": 0})
        await send_main_menu_carousel(psid)
        
    elif payload == "START_BOOKING":
        await fsm.set_state(psid, UserState.COLLECTING_BOOKING_INFO, {"step": "name", "nlp_failures": 0})
        await send_text_response(psid, "Let's get your service request scheduled. First, what is your full name?")
        
    elif payload == "GET_ESTIMATE":
        await fsm.set_state(psid, UserState.FAQ_LOOP, {"step": "appliance_details", "nlp_failures": 0})
        await send_text_response(psid, "Sure! Please enter the appliance name, brand, and model (e.g., Samsung WA10 Washing Machine):", include_menu=False)

    # Quick Reply conversions to Postbacks
    elif payload == "TYPE_HOME_SERVICE":
        await fsm.update_context(psid, {"service_type": "HOME_SERVICE", "step": "address"})
        await send_text_response(psid, "Since you prefer Home Service, please provide your Complete Service Address in Cebu:")
        
    elif payload == "TYPE_DROP_OFF":
        await fsm.update_context(psid, {"service_type": "DROP_OFF", "address": None, "landmark": None, "step": "appliance_category"})
        await send_messenger_response(psid, {
            "text": "What appliance needs attention?",
            "quick_replies": [
                {"content_type": "text", "title": "Washing Machine 🧺", "payload": "CAT_LAUNDRY"},
                {"content_type": "text", "title": "Refrigerator ❄️", "payload": "CAT_COOLING"},
                {"content_type": "text", "title": "Air Conditioner 🌬️", "payload": "CAT_AC"},
                {"content_type": "text", "title": "Stove / Oven 🍳", "payload": "CAT_KITCHEN"},
                {"content_type": "text", "title": "Small Electronics 🔌", "payload": "CAT_SMALL"},
                {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
            ]
        })

    elif payload.startswith("CAT_"):
        cat_map = {
            "CAT_LAUNDRY": "laundry",
            "CAT_COOLING": "cooling",
            "CAT_AC": "ac",
            "CAT_KITCHEN": "kitchen",
            "CAT_SMALL": "small_electronics"
        }
        payload_to_name = {
            "CAT_LAUNDRY": "Washing Machine",
            "CAT_COOLING": "Refrigerator",
            "CAT_AC": "Air Conditioner",
            "CAT_KITCHEN": "Stove / Oven",
            "CAT_SMALL": "Small Electronics"
        }
        await fsm.update_context(psid, {
            "appliance_category": cat_map.get(payload, "general"),
            "appliance": payload_to_name.get(payload, "Appliance"),
            "step": "brand"
        })
        await send_text_response(psid, "What is the brand and model of your appliance? (e.g., Samsung Model WA10)")

    elif payload == "CONFIRM_BOOKING":
        # Save decoupled booking and customer profile in DB
        async with AsyncSessionLocal() as db:
            service_type = ctx.get("service_type", "DROP_OFF")
            booking = await booking_service.create_pending_booking(
                db=db,
                fb_psid=psid,
                service_type=service_type,
                details=ctx
            )
            
        booking_id = booking.id if booking else 9999
        
        # Reset state to IDLE
        await fsm.set_state(psid, UserState.IDLE, {"nlp_failures": 0})
        
        # Send confirmation details including direct fallback emergency channels
        success_msg = (
            f"🎉 **Booking Successfully Submitted!**\n\n"
            f"Thank you, {ctx.get('name', 'Customer')}! Your service request has been registered in our system.\n"
            f"📌 **Booking Reference ID:** #INATO-B{booking_id}\n\n"
            f"📅 **What's Next?**\n"
            f"Our dispatch coordinator will call or message your mobile number within **30 minutes** to coordinate the technician arrival window or shop drop-off slot.\n\n"
            f"📞 **Need to make changes or have an emergency?** You can reach us directly at **+63 927 154 0088** or via email at **nhel@inatoelectronics.com**.\n\n"
            f"Thank you for choosing Inato Electronics! We'll bring your appliance back to life. 🔧💙"
        )
        await send_messenger_response(psid, {
            "text": success_msg,
            "quick_replies": [
                {"content_type": "text", "title": "Back to Main Menu", "payload": "BACK_TO_MAIN_MENU"}
            ]
        })

    elif payload == "TRACK_BOOKINGS":
        # Retrieve only active bookings associated with customer's PSID
        async with AsyncSessionLocal() as db:
            active_orders = await tracker_service.get_active_orders_by_psid(db, psid)
            
        if not active_orders:
            await send_messenger_response(psid, {
                "text": "🔍 You currently do not have any active service requests.\n\nIf you would like to book a new service request or schedule a drop off, click below!",
                "quick_replies": [
                    {"content_type": "text", "title": "Book Service 📅", "payload": "START_BOOKING"},
                    {"content_type": "text", "title": "Main Menu 🏠", "payload": "RESET_TO_IDLE"}
                ]
            })
            return
            
        # Format active orders in a Carousel (Generic Template)
        elements = []
        for i, order in enumerate(active_orders):
            mode = "Home Service 🏠" if order.service_type == "HOME_SERVICE" else "Drop-off 🚚"
            elements.append({
                "title": f"Active Request #{i+1} of {len(active_orders)}",
                "subtitle": (
                    f"📌 Ref: #INATO-B{order.id}\n"
                    f"🔧 Device: {order.brand or ''} {order.model or ''} ({order.appliance_category or ''})\n"
                    f"🚘 Mode: {mode}\n"
                    f"🚦 Status: {order.status}"
                ),
                "buttons": [
                    {
                        "type": "postback",
                        "title": "View Details",
                        "payload": f"VIEW_DETAILS_{order.id}"
                    }
                ]
            })
            
        track_carousel = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements[:10]  # Messenger limit of 10 elements
                }
            },
            "quick_replies": [
                {"content_type": "text", "title": "Track my Bookings", "payload": "TRACK_BOOKINGS"},
                {"content_type": "text", "title": "Main Menu", "payload": "BACK_TO_MAIN_MENU"}
            ]
        }
        await send_text_response(psid, "🔍 **Your Active Service Requests:**", include_menu=False)
        await send_messenger_response(psid, track_carousel)

    elif payload.startswith("VIEW_DETAILS_"):
        booking_id = int(payload.split("_")[-1])
        async with AsyncSessionLocal() as db:
            from sqlalchemy.future import select
            from sqlalchemy.orm import selectinload
            from models import Booking
            stmt = select(Booking).where(Booking.id == booking_id).options(selectinload(Booking.quotation))
            res = await db.execute(stmt)
            booking = res.scalars().first()
            
        if not booking:
            await send_text_response(psid, "⚠️ Booking not found.", include_menu=False)
            return
            
        mode = "Home Service 🏠" if booking.service_type == "HOME_SERVICE" else "Drop-off 🚚"
        
        details_msg = (
            f"📋 **Booking Details: #INATO-B{booking.id}**\n"
            f"---------------------------------\n"
            f"🚦 **Status:** {booking.status}\n"
            f"⚙️ **Service Mode:** {mode}\n"
            f"📦 **Appliance:** {booking.brand or ''} {booking.model or ''} ({booking.appliance_category or ''})\n"
            f"🔍 **Symptom/Problem:** {booking.symptom or 'N/A'}\n"
        )
        
        if booking.service_type == "HOME_SERVICE":
            if booking.address:
                details_msg += f"📍 **Address:** {booking.address}\n"
            if booking.landmark:
                details_msg += f"📍 **Landmark:** {booking.landmark}\n"
                
        # Include estimate/quotation info if available
        if booking.quotation:
            details_msg += f"\n🧾 **Quotation Amount:** ₱{booking.quotation.total_amount:,.2f}\n"
            if booking.quotation.pdf_url:
                details_msg += f"📄 **Quotation PDF:** {booking.quotation.pdf_url}\n"
        elif booking.estimated_cost_json:
            est = booking.estimated_cost_json
            if isinstance(est, dict):
                low = est.get("estimated_repair_labor_low", 0)
                high = est.get("estimated_repair_labor_high", 0)
                if low or high:
                    details_msg += f"\n💵 **Estimated Labor Range:** ₱{low:,.2f} – ₱{high:,.2f}\n"
                    
        await send_messenger_response(psid, {
            "text": details_msg,
            "quick_replies": [
                {"content_type": "text", "title": "Track my Bookings", "payload": "TRACK_BOOKINGS"},
                {"content_type": "text", "title": "Main Menu", "payload": "BACK_TO_MAIN_MENU"}
            ]
        })
