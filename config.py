from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    unusual_whales_key: str = ""
    benzinga_key: str = ""
    broker_api_key: str = ""

    # System
    environment: str = "paper"
    log_level: str = "INFO"

    # Hard Limits
    max_single_position_pct: float = 0.25
    max_open_positions: int = 5
    max_daily_new_trades: int = 3
    min_conviction: float = 0.60
    max_uncertainty: float = 0.70
    max_sector_exposure: float = 0.40
    max_thematic_exposure: float = 0.40

    # Feature Flags
    fda_biotech_enabled: bool = False
    twitter_enabled: bool = False
    reddit_enabled: bool = True
    memory_enabled: bool = True
    agent_trading_enabled: bool = False  # MVP-3'te açılacak

    class Config:
        env_file = ".env"

settings = Settings()
# Paper trade sanal sermaye
paper_capital: float = 10000.0
