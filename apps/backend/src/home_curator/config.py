from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supervisor_token: str | None = Field(default=None, alias="SUPERVISOR_TOKEN")
    ha_token: str | None = Field(default=None, alias="HA_TOKEN")
    ha_url: str | None = Field(default=None, alias="HA_URL")
    config_dir: Path | None = Field(default=None, alias="CONFIG_DIR")
    data_dir: Path | None = Field(default=None, alias="DATA_DIR")

    @field_validator("ha_token", mode="before")
    @classmethod
    def _default_ha_token(cls, v, info):
        if v:
            return v
        return info.data.get("supervisor_token")

    @field_validator("ha_url", mode="before")
    @classmethod
    def _default_ha_url(cls, v, info):
        if v:
            return v
        return "http://supervisor/core" if info.data.get("supervisor_token") else "http://localhost:8123"

    @field_validator("config_dir", mode="before")
    @classmethod
    def _default_config_dir(cls, v, info):
        if v:
            return Path(v)
        if info.data.get("supervisor_token"):
            return Path("/config/home-curator")
        return Path.cwd() / ".dev-config" / "home-curator"

    @field_validator("data_dir", mode="before")
    @classmethod
    def _default_data_dir(cls, v, info):
        if v:
            return Path(v)
        if info.data.get("supervisor_token"):
            return Path("/data")
        return Path.cwd() / ".dev-data"

    @property
    def effective_token(self) -> str | None:
        return self.supervisor_token or self.ha_token

    @property
    def db_path(self) -> Path:
        return self.data_dir / "curator.db"

    @property
    def policies_path(self) -> Path:
        return self.config_dir / "policies.yaml"
