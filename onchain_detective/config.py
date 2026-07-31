from pydantic_settings import BaseSettings
from pydantic import Field, validator
from pathlib import Path
from typing import Optional, Literal


class Settings(BaseSettings):
    """Глобальные настройки фреймворка. Читает из .env и переменных окружения."""

    # ── Пути ──────────────────────────────────────────────
    BASE_DIR: Path = Field(default=Path(__file__).parent.parent)
    DATA_DIR: Path = Field(default=Path(__file__).parent.parent / "data")
    NOTEBOOKS_DIR: Path = Field(default=Path(__file__).parent.parent / "notebooks")

    # ── API ключи ─────────────────────────────────────────
    ETHERSCAN_API_KEY: str = Field(default="", description="API ключ Etherscan")
    MORALIS_API_KEY: str = Field(default="", description="API ключ Moralis")
    ARKHAM_API_KEY: str = Field(default="", description="API ключ Arkham (опционально)")
    OPENAI_API_KEY: str = Field(default="", description="API ключ OpenAI для AI-интерпретатора")

    # ── Telegram ──────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Токен Telegram-бота")
    TELEGRAM_CHAT_ID: str = Field(default="", description="ID чата для алертов")

    # ── Сеть ──────────────────────────────────────────────
    NETWORK: Literal["ethereum", "bsc", "polygon", "arbitrum", "optimism"] = "ethereum"
    
    @property
    def etherscan_base_url(self) -> str:
        urls = {
            "ethereum": "https://api.etherscan.io/v2/api",
            "bsc": "https://api.bscscan.com/v2/api",
            "polygon": "https://api.polygonscan.com/v2/api",
            "arbitrum": "https://api.arbiscan.io/v2/api",
            "optimism": "https://api-optimistic.etherscan.io/v2/api",
        }
        return urls[self.NETWORK]

    # ── AI настройки ──────────────────────────────────────
    AI_MODEL: str = Field(default="gpt-4o-mini", description="Модель OpenAI")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1", description="Базовый URL OpenAI API")
    AI_TEMPERATURE: float = Field(default=0.3, description="Температура генерации")
    AI_MAX_TOKENS: int = Field(default=1000, description="Максимальное количество токенов в ответе")
    AI_LANGUAGE: str = Field(default="russian", description="Язык отчётов")

    # ── Лимиты ────────────────────────────────────────────
    RATE_LIMIT_CALLS: int = Field(default=5, description="Максимум запросов к API в секунду")
    MAX_WALLETS_TO_ANALYZE: int = Field(default=500, description="Максимум кошельков для кластеризации")
    WHALE_MIN_BALANCE_USD: float = Field(default=1_000_000, description="Минимальный баланс кита в USD")
    INSIDER_EARLY_BLOCKS: int = Field(default=100, description="Сколько блоков считать 'ранней закупкой'")
    
    # ── Кеширование ───────────────────────────────────────
    CACHE_ENABLED: bool = Field(default=True, description="Включить кеширование запросов")
    CACHE_TTL_SECONDS: int = Field(default=3600, description="Время жизни кеша (1 час по умолчанию)")

    # ── Логирование ──────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── Экспериментальные модули (для Pro версии) ────────
    ENABLE_WHALE_MONITOR: bool = Field(default=False, description="Включить монитор китов")
    ENABLE_ARKHAM: bool = Field(default=False, description="Включить интеграцию с Arkham")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Создаём папки, если их нет
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


# Синглтон — единственный экземпляр настроек для всего фреймворка
settings = Settings()