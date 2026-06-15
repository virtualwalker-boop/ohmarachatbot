from enum import Enum
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models import Customer

class UserState(str, Enum):
    IDLE = "IDLE"
    FAQ_LOOP = "FAQ_LOOP"
    COLLECTING_BOOKING_INFO = "COLLECTING_BOOKING_INFO"
    ESTIMATING_COST = "ESTIMATING_COST"
    QUOTATION_GENERATED = "QUOTATION_GENERATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"

class StateMachine:
    async def get_state(self, psid: str) -> UserState:
        async with AsyncSessionLocal() as db:
            stmt = select(Customer).where(Customer.fb_psid == psid)
            result = await db.execute(stmt)
            customer = result.scalars().first()
            if customer and customer.fsm_state:
                try:
                    return UserState(customer.fsm_state)
                except ValueError:
                    return UserState.IDLE
            return UserState.IDLE

    async def set_state(self, psid: str, state: UserState, context: dict = None):
        if context is None:
            context = {}
        async with AsyncSessionLocal() as db:
            stmt = select(Customer).where(Customer.fb_psid == psid)
            result = await db.execute(stmt)
            customer = result.scalars().first()
            if not customer:
                customer = Customer(fb_psid=psid)
                db.add(customer)
            customer.fsm_state = state.value
            customer.fsm_context = context
            db.add(customer)
            await db.commit()

    async def get_context(self, psid: str) -> dict:
        async with AsyncSessionLocal() as db:
            stmt = select(Customer).where(Customer.fb_psid == psid)
            result = await db.execute(stmt)
            customer = result.scalars().first()
            if customer and customer.fsm_context:
                return customer.fsm_context
            return {}

    async def update_context(self, psid: str, new_context: dict):
        async with AsyncSessionLocal() as db:
            stmt = select(Customer).where(Customer.fb_psid == psid)
            result = await db.execute(stmt)
            customer = result.scalars().first()
            if not customer:
                customer = Customer(fb_psid=psid)
                db.add(customer)
            
            current_context = customer.fsm_context or {}
            # Update context dictionary
            updated_context = dict(current_context)
            updated_context.update(new_context)
            customer.fsm_context = updated_context
            db.add(customer)
            await db.commit()

fsm = StateMachine()

