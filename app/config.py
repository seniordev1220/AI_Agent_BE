from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    PERPLEXITY_API_KEY: str
    ADMIN_DATABASE_URL: str
    USER_DATABASE_URL_BASE: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PUBLIC_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
