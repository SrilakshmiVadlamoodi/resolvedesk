from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./data/resolvedesk.db"
    session_secret: str = "dev-only-insecure-secret-change-me"

    class Config:
        env_file = ".env"


settings = Settings()
