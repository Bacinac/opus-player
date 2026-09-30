import opus_auth
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Infra bootstrap, read from env at startup. User-editable settings (DIDA,
    playback targets) live in the DB — see opus.settings_store."""

    model_config = {"env_prefix": "OPUS_", "hide_input_in_errors": True}

    database_url: str = Field(min_length=1)
    cookie_domain: str = ""
    # what sessions are signed with, the same in all three modules. There is no
    # fallback: without it no person, car or ticket could be recognised.
    session_key: str = Field(min_length=opus_auth.SESSION_KEY_MIN)
    # where Library answers and the service token it is asked with. There is no
    # player without them: everything it shows, and everybody it lets in, is
    # asked of Library.
    library_url: str = Field(min_length=1)
    library_token: str = Field(min_length=1)
    # where fetched artwork is kept, sized for the screen that asked, and how
    # much of it; past that the pictures looked at longest ago go first
    art_cache: str = "/art"
    art_cache_bytes: int = Field(2 * 1024**3, gt=0)


settings = Settings()
