from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    github_models_token: str = ""
    together_api_key: str = ""
    database_url: str = "sqlite:///./data/resolvedesk.db"
    session_secret: str = "dev-only-insecure-secret-change-me"
    allowed_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
