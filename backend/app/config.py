from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Application
    app_name: str = "PersonalKB"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/personal_kb.db"

    # File storage
    upload_dir: Path = Path("./data/uploads")
    max_file_size_mb: int = 50

    # NLP
    nlp_language: str = "zh"

    # LLM (Claude API)
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    auto_analyze: bool = True

    # UI
    language: str = "zh-CN"
    theme: str = "system"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
