from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    geo_master_key: str
    wechat_mch_id: str = ""
    wechat_app_id: str = ""
    wechat_api_v3_key: str = ""
    wechat_private_key: str = ""
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""


settings = Settings()
