"""
Centralized application configuration.
Reads from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider selection. This is only the DEFAULT/fallback — the actual
    # active provider is stored in runtime_settings.py so an admin can change
    # it without restarting the server. Valid values: groq | gemini | qwen | grok_drive
    AI_PROVIDER: str = "groq"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-plus"
    # DashScope's OpenAI-compatible endpoint. Use the intl one unless your
    # account/region requires the mainland China endpoint.
    QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    # --- Grok-via-Google-Drive provider ---
    # This provider doesn't call an API directly. Instead it writes a task
    # file to a shared Drive folder, waits for a scheduled Grok Task (set up
    # separately at grok.com/tasks, with Grok's own Drive connector) to pick
    # it up and write a result file back, then reads that result.
    #
    # Auth is OAuth as your own Google account (NOT a service account —
    # service accounts have zero Drive storage quota and can't create files,
    # even in a folder shared with them). Run scripts/get_drive_token.py once
    # to produce the token file below.
    GOOGLE_OAUTH_CLIENT_SECRETS_FILE: str = ""  # "Desktop app" OAuth client JSON from Cloud Console
    GOOGLE_OAUTH_TOKEN_FILE: str = "./credentials/drive_token.json"  # created by the setup script
    GOOGLE_DRIVE_FOLDER_ID: str = ""       # a folder already in your own Drive
    GROK_DRIVE_POLL_INTERVAL_SECONDS: int = 15
    GROK_DRIVE_MAX_WAIT_SECONDS: int = 1800  # give the scheduled task time to run

    # --- Admin panel ---
    # Shared-secret token required in the X-Admin-Token header to view/change
    # the active AI provider. Regular users never see or touch this.
    ADMIN_TOKEN: str = ""

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    ALLOWED_ORIGINS: str = "*"

    CHUNK_MAX_WORDS: int = 900
    CHUNK_OVERLAP_WORDS: int = 80

    URL_FETCH_TIMEOUT: int = 15
    LLM_REQUEST_TIMEOUT: int = 60

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
