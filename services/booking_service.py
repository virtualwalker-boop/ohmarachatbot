from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Booking, Customer
from typing import Optional

class BookingService:
    async def check_availability(self, date: str) -> bool:
        # Mock availability logic
        return True
        
    async def create_pending_booking(
        self, 
        db: AsyncSession, 
        fb_psid: str, 
        service_type: str, 
        details: dict
    ) -> Optional[Booking]:
        # 1. Get or create Customer (CRM decoupling)
        stmt = select(Customer).where(Customer.fb_psid == fb_psid)
        result = await db.execute(stmt)
        customer = result.scalars().first()
        
        first_name = details.get("first_name", "Valued")
        last_name = details.get("last_name", "Customer")
        contact_number = details.get("phone")
        
        if not customer:
            customer = Customer(
                fb_psid=fb_psid,
                first_name=first_name,
                last_name=last_name,
                contact_number=contact_number
            )
            db.add(customer)
            await db.flush()  # Get customer.id
        else:
            # Update CRM details if provided
            if contact_number:
                customer.contact_number = contact_number
            if first_name and first_name != "Valued":
                customer.first_name = first_name
            if last_name and last_name != "Customer":
                customer.last_name = last_name
            db.add(customer)
            
        # 2. Create dynamic Booking record (with request-specific address/landmark)
        new_booking = Booking(
            customer_id=customer.id,
            status="PENDING",
            service_type=service_type,
            appliance_category=details.get("appliance_category"),
            brand=details.get("brand"),
            model=details.get("model"),
            symptom=details.get("symptom"),
            address=details.get("address"),
            landmark=details.get("landmark"),
            estimated_cost_json=details.get("estimated_cost_json")
        )
        db.add(new_booking)
        await db.commit()
        await db.refresh(new_booking)
        return new_booking

booking_service = BookingService()
