import os


class Config:
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL", "amqp://admin:admin@localhost:5672//"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_KEY: str = os.getenv("REDIS_KEY", "challenge_pool")

    POOL_TARGET_SIZE: int = int(os.getenv("POOL_TARGET_SIZE", "50"))
    POOL_MIN_SIZE: int = int(os.getenv("POOL_MIN_SIZE", "10"))
    REFILL_INTERVAL_S: int = int(os.getenv("REFILL_INTERVAL_S", "30"))

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    ENABLE_LLM: bool = os.getenv("ENABLE_LLM", "true").lower() == "true"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    CB_RECOVERY_TIMEOUT_S: int = int(os.getenv("CB_RECOVERY_TIMEOUT_S", "120"))

    TASK_MAX_RETRIES: int = int(os.getenv("TASK_MAX_RETRIES", "3"))
    TASK_RETRY_DELAY_S: int = int(os.getenv("TASK_RETRY_DELAY_S", "10"))


config = Config()
