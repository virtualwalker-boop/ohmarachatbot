import os
import re

class FAQService:
    def __init__(self):
        self.kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledgebase.md")
        self.sections = {}
        self.load_knowledgebase()

    def load_knowledgebase(self):
        """Loads and parses knowledgebase.md into logical sections."""
        if not os.path.exists(self.kb_path):
            # Fallback mock data if file not found
            self.sections = {
                "general": "Inato Electronics: Specializing in repair and technical servicing of laundry, commercial, and household appliances."
            }
            return

        with open(self.kb_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split sections by '#' headers
        raw_sections = re.split(r'\n#\s+', "\n" + content)
        for section in raw_sections:
            if not section.strip():
                continue
            lines = section.split("\n")
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            self.sections[title.upper()] = body

    def get_answer(self, query: str) -> str:
        query_lower = query.lower()

        def match_keywords(keywords: list) -> bool:
            for kw in keywords:
                if len(kw) <= 2:
                    if re.search(rf'\b{re.escape(kw)}\b', query_lower):
                        return True
                else:
                    if kw in query_lower:
                        return True
            return False

        # 1. Location & Contact Info
        if match_keywords(["location", "address", "where", "contact", "phone", "number", "email", "call"]):
            contact_sec = self.sections.get("CONTACT AND LOCATION METADATA", "")
            profile_sec = self.sections.get("BUSINESS PROFILE & CORE IDENTITY", "")
            street = re.search(r"STREET ADDRESS:\s*(.*)", contact_sec)
            phone = re.search(r"CONTACT MOBILE PHONE:\s*(.*)", contact_sec)
            email = re.search(r"OFFICIAL EMAIL ADDRESS:\s*(.*)", contact_sec)
            
            response = "🔧 **Inato Electronics Contact & Location:**\n"
            if street: response += f"📍 **Address**: {street.group(1)}\n"
            if phone: response += f"📞 **Mobile**: {phone.group(1)}\n"
            if email: response += f"✉️ **Email**: {email.group(1)}\n"
            response += "\nTo book a repair service, please message us directly on our official Facebook Page (https://web.facebook.com/inatoelectronics) or call us!"
            return response

        # 2. Privacy & Data Compliance
        if match_keywords(["privacy", "data", "privacy act", "complian", "security", "protect"]):
            privacy_sec = self.sections.get("PRIVACY, DATA COMPLIANCE, AND SECURITY", "")
            return f"🔒 **Data Privacy & Compliance (Republic Act No. 10173):**\n{privacy_sec}"

        # 3. Booking & Operations
        if match_keywords(["book", "sched", "repair", "service", "appoint", "home service", "visit"]):
            booking_sec = self.sections.get("OPERATIONS AND BOOKING WORKFLOW", "")
            return f"📅 **How to Book a Repair Service:**\n{booking_sec}"

        # 4. Small Electronics / Fans
        if match_keywords(["fan", "microwave", "rice cooker", "blender", "fuse"]):
            if "fan" in query_lower:
                return "🔌 **Electric Fan Servicing (Industrial & Stand Fans):**\nWe do electric motor rewinding, replacement of degraded motor run capacitors, cleaning/lubrication of seized shaft bushings, or total motor assembly rebuilding."
            if match_keywords(["microwave", "rice", "blender"]):
                return "🍲 **Small Kitchen Electronics:**\nFor microwave ovens, rice cookers, and everyday appliances, we identify blown thermal fuses, replace faulty magnetrons, repair control door switches, or replace defective main PCBs."
            return "🔌 **Small Household Electronics:**\nWe service electric fans, microwave ovens, rice cookers, blenders, and other essential household electronics."

        # 5. Kitchen / Stove / Oven symptoms
        if match_keywords(["kitchen", "stove", "range", "oven", "ignit", "heat", "burner"]):
            return "🍳 **Kitchen Appliance Repairs:**\nWe service gas ranges, built-in ovens, commercial and household stoves. We inspect and clean clogged burner orifices, replace faulty spark ignition modules, repair broken safety valves, or swap failed electrical heating elements."

        # 6. Refrigeration & Air Conditioning symptoms
        if match_keywords(["fridge", "refrigerator", "cooler", "chiller", "cooling", "freeze", "compressor", "aircon", "air cond", "ac", "warm air", "airflow"]):
            if match_keywords(["cool", "freeze", "cold", "fridge", "refrigerator", "chiller"]):
                return "❄️ **Refrigerator / Chiller Not Cooling:**\nWe offer defrost system diagnostics, thermostat replacement, start relay replacement, evaporator fan motor replacement, or advanced compressor unit repairs."
            if match_keywords(["aircon", "ac", "air cond", "warm", "airflow"]):
                return "🌬️ **Air Conditioner Repairs:**\nWe perform periodic deep cleaning and general maintenance, fix control board electrical failures, replace faulty run capacitors, or resolve air restrictions."
            return "❄️ **Refrigeration & AC Servicing:**\nWe repair household refrigerators, commercial chillers, window-type ACs, and split-type AC units."

        # 7. Laundry / Washing Machine symptoms
        if match_keywords(["laundry", "washer", "washing", "leak", "spin", "drum", "drain", "vibrat", "banging", "noise"]):
            laundry_sec = self.sections.get("TECHNICAL REPAIR DOMAIN 1: LAUNDRY SHOP EQUIPMENT & WASHING MACHINES", "")
            if "leak" in query_lower:
                return "💧 **Leaking Washer Diagnostics & Repair:**\nWe inspect and replace door bellows gaskets, faulty water inlet valves, damaged internal tubs, or deteriorated drain hoses."
            if match_keywords(["spin", "drum", "turn"]):
                return "🔄 **Washer Drum / Spin Repair:**\nWe perform a complete diagnostic evaluation and replace worn-out drive belts, faulty drive motors, broken lid switches, door locks, or failed mechanical gearboxes/transmissions."
            if "drain" in query_lower:
                return "🚰 **Washer Drainage Issue:**\nWe resolve draining issues by unclogging/replacing blocked drain pumps, clearing internal drain filters, or repairing electrical wiring faults to the pump assembly."
            if match_keywords(["vibration", "banging", "noise", "loud"]):
                return "🔊 **Loud Noise / Vibration Repair:**\nWe inspect and replace broken suspension rods, worn shock absorbers, or unbalanced load sensor microswitches."
            return f"🧺 **Laundry & Washing Machine Repairs:**\nWe service commercial laundry setups and residential washing machines (top-load, front-load, twin tubs). Technical Scope:\n{laundry_sec}"

        # Fallback
        return (
            "👋 **Welcome to Inato Electronics!** 🔧\n\n"
            "We provide fast, reliable, and affordable repairs for household and commercial appliances "
            "with local \"Inato\" care—including convenient Home Service! 🏠\n\n"
            "How can we help you today?"
        )

faq_service = FAQService()

