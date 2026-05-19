from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = 'sqlite:///./hotelrm.db'
    admin_api_key: str = 'change-me'
    env: str = 'development'
    default_rate_source_mode: str = 'hybrid'
    user_web_origin: str = 'http://localhost:5174'
    admin_web_origin: str = 'http://localhost:5173'

    class Config:
        env_file = '.env'
        extra = 'ignore'


settings = Settings()
