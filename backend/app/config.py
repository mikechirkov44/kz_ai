from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kz-ai-analytics"
    app_env: str = "development"
    secret_key: str = "dev-secret-key-change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    database_url: str = "postgresql+psycopg://kz_ai:kz_ai@localhost:5432/kz_ai"
    redis_url: str = "redis://localhost:6379/0"

    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"

    odata_asil_url: str = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
    odata_asil_user: str = ""
    odata_asil_password: str = ""
    odata_asil_verify_ssl: bool = False

    odata_miamor_url: str = ""
    odata_miamor_user: str = ""
    odata_miamor_password: str = ""
    odata_miamor_verify_ssl: bool = False

    sync_enabled: bool = False

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    digest_email: str = "s.bacherikova@yandex.ru"
    timezone: str = "Asia/Almaty"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    upload_dir: str = "uploads"
    max_upload_mb: int = 10
    max_upload_rows: int = 50_000
    rate_limit_login_per_minute: int = 10
    rate_limit_api_per_minute: int = 180
    export_max_rows: int = 10_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
