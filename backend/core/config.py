"""Core application configuration.
All configurable parameters loaded from environment variables with sensible defaults.
"""

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = Field(default="demo", description="demo | development | production | test")
    DATABASE_URL: str = Field(default="sqlite:///./sgsu_nexus.db")
    
    # Auth
    JWT_SECRET: str = Field(default="sgsu-demo-jwt-secret-key-2026-very-secure")
    JWT_TTL_HOURS: int = Field(default=8)
    JWT_ALGORITHM: str = Field(default="HS256")
    
    # CORS & Web
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
    FRONTEND_ORIGIN: str = Field(default="http://localhost:5173")
    
    # AI Gateway
    AI_PROVIDER: str = Field(default="gemini")
    AI_MODEL: str = Field(default="gemini-2.5-flash")
    AI_TIMEOUT_S: float = Field(default=25.0)
    AI_FORCE_FALLBACK: bool = Field(default=False)
    
    GEMINI_API_KEY_1: str = Field(default="")
    GEMINI_API_KEY_2: str = Field(default="")
    GROK_API_KEY: str = Field(default="")
    
    # Classroom & Pedagogy
    ALLOW_AUDIENCE_JOIN: bool = Field(default=False)
    
    # Mastery & Assessment Thresholds
    MASTERY_STRONG: int = Field(default=70)
    MASTERY_DEVELOPING: int = Field(default=50)
    GAP_MIN_SHARE: float = Field(default=0.40)
    GAP_MIN_RESPONDENTS: int = Field(default=10)
    PRIOR_WEIGHT: float = Field(default=2.0)
    
    # Evidence Weights
    W_EXIT_QUIZ: float = Field(default=0.8)
    W_LIVE_POLL: float = Field(default=0.5)
    W_PRACTICE: float = Field(default=0.4)
    
    # Privacy & Governance
    MIN_GROUP_SIZE: int = Field(default=5)
    
    # Rate Limiting
    RATE_LIMIT_AI_PER_MIN: int = Field(default=10)
    RATE_LIMIT_GENERAL_PER_MIN: int = Field(default=120)

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def validate_production_security(self) -> None:
        default_secret = "sgsu-demo-jwt-secret-key-2026-very-secure"
        if self.APP_ENV not in ("demo", "development", "test") and self.JWT_SECRET == default_secret:
            raise ValueError("Production mode requires non-default JWT_SECRET")


settings = Settings()
settings.validate_production_security()
