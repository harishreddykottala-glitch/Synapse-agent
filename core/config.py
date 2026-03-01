"""Configuration management for Synapse Agent."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Central configuration loaded from environment variables."""

    # LLM
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "google_genai"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.0-flash"))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    xai_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))

    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
    )

    # Database
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "./data/synapse.db"))

    # Agent limits
    max_adaptations: int = field(default_factory=lambda: int(os.getenv("MAX_ADAPTATIONS", "3")))
    max_steps: int = field(default_factory=lambda: int(os.getenv("MAX_STEPS", "20")))
    verbose: bool = field(default_factory=lambda: os.getenv("VERBOSE", "true").lower() == "true")

    # Search (optional)
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
