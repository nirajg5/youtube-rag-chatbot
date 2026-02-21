"""
Configuration module for YouTube RAG Chatbot
Centralized configuration management using environment variables
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        env="OPENROUTER_BASE_URL"
    )
    
    # Model Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small",
        env="EMBEDDING_MODEL"
    )
    chat_model: str = Field(
        default="openai/gpt-4o-mini",
        env="CHAT_MODEL"
    )
    
    # RAG Configuration
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE", ge=100, le=5000)
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP", ge=0, le=1000)
    retrieval_k: int = Field(default=4, env="RETRIEVAL_K", ge=1, le=10)
    
    # LLM Configuration
    llm_temperature: float = Field(default=0.2, env="LLM_TEMPERATURE", ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1000, env="LLM_MAX_TOKENS", ge=100, le=4000)
    llm_timeout: int = Field(default=30, env="LLM_TIMEOUT", ge=10, le=120)
    
    # Server Configuration
    server_host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    server_port: int = Field(default=8000, env="SERVER_PORT", ge=1000, le=65535)
    server_reload: bool = Field(default=False, env="SERVER_RELOAD")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["*"],
        env="ALLOWED_ORIGINS"
    )
    
    @validator('chunk_overlap')
    def validate_overlap(cls, v, values):
        """Ensure chunk overlap is less than chunk size"""
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v
    
    @validator('allowed_origins', pre=True)
    def parse_origins(cls, v):
        """Parse comma-separated origins"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create settings instance (singleton pattern)
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience function to reload settings
def reload_settings():
    """Reload settings from environment"""
    global _settings
    _settings = Settings()
    return _settings


# Export settings instance
settings = get_settings()
