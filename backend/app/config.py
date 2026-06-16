from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    github_app_id: int
    github_private_key: str
    github_webhook_secret: str
    github_client_id: str = ""
    github_client_secret: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    mongodb_uri: str
    port: int = 8000
    railway_url: str = ""

    @field_validator("github_private_key")
    @classmethod
    def fix_private_key(cls, v: str) -> str:
        # Railway stores multiline env vars with literal \n — convert back
        return v.replace("\\n", "\n")

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
