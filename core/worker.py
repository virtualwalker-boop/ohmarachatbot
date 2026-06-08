import asyncio
from arq import Worker
from arq.connections import RedisSettings
from core.config import settings

async def generate_pdf_task(ctx, booking_id: int):
    # This task will be picked up by the ARQ worker
    from services.billing.document_service import generate_quotation_pdf
    print(f"Generating PDF for booking {booking_id}...")
    await generate_quotation_pdf(booking_id)
    return True

async def sync_crm_task(ctx, user_id: int):
    # Placeholder task for CRM sync
    print(f"Syncing user {user_id} with CRM...")
    return True

class WorkerSettings:
    functions = [generate_pdf_task, sync_crm_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

# To run: arq core.worker.WorkerSettings
