from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Ohmara Chatbot"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot"

    # Redis (For FSM state caching)
    redis_url: str = "redis://localhost:6379/0"

    # Meta Messenger
    meta_verify_token: str = "my_secure_verify_token"
    meta_page_access_token: str = "YOUR_PAGE_ACCESS_TOKEN"

    # Google Maps
    google_maps_api_key: str = "YOUR_GOOGLE_MAPS_API_KEY"

    # Google GenAI (Gemini)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Stripe
    stripe_api_key: str = "sk_test_..."
    stripe_webhook_secret: str = "whsec_..."

    # HubSpot / CRM
    crm_api_key: str = "crm_..."

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
