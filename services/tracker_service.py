from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Booking, Customer

class TrackerService:
    async def get_active_orders_by_psid(self, db: AsyncSession, fb_psid: str):
        """
        Retrieves all currently active bookings for the specified customer PSID.
        Excludes already completed, closed, or cancelled bookings.
        """
        # 1. Resolve Customer ID first
        stmt_cust = select(Customer).where(Customer.fb_psid == fb_psid)
        res_cust = await db.execute(stmt_cust)
        customer = res_cust.scalars().first()
        if not customer:
            return []
            
        # 2. Query bookings that are in an active state
        stmt_booking = select(Booking).where(
            Booking.customer_id == customer.id,
            Booking.status.in_(["PENDING", "CONFIRMED", "DIAGNOSED", "IN_PROGRESS"])
        )
        res_booking = await db.execute(stmt_booking)
        return res_booking.scalars().all()

tracker_service = TrackerService()
