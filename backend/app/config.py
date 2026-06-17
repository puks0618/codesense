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
        # Railway may store the PEM with literal \n sequences — convert them back
        v = v.replace("\\n", "\n")
        # If the key still has no real newlines (all on one line), reconstruct it:
        # strip the header/footer, split the base64 into 64-char lines, re-wrap
        if "\n" not in v:
            header = "-----BEGIN RSA PRIVATE KEY-----"
            footer = "-----END RSA PRIVATE KEY-----"
            body = v.replace(header, "").replace(footer, "").strip()
            lines = [body[i:i+64] for i in range(0, len(body), 64)]
            v = header + "\n" + "\n".join(lines) + "\n" + footer + "\n"
        return v

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
