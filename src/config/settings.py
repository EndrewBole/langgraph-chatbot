import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Evolution API WhatsApp
    EVOLUTION_API_URL: str = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
    EVOLUTION_API_KEY: str = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INSTANCE_NAME: str = os.getenv("EVOLUTION_INSTANCE_NAME", "temporalis")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # RAG
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    RAG_SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.40"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "10"))
    RAG_RERANK_TOP_N: int = int(os.getenv("RAG_RERANK_TOP_N", "3"))
    DATA_DIR: str = os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data"))

    # Timings
    HUMAN_HANDOFF_TIMEOUT_MINUTES: int = int(os.getenv("HUMAN_HANDOFF_TIMEOUT_MINUTES", "10"))
    MESSAGE_BUFFER_WAIT_SECONDS: int = int(os.getenv("MESSAGE_BUFFER_WAIT_SECONDS", "7"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    RATE_LIMIT_MAX: int = int(os.getenv("RATE_LIMIT_MAX", "10"))

    # Human Handoff Loop
    STORE_OWNER_PHONE: str = os.getenv("STORE_OWNER_PHONE", "")
    HUMAN_RELEASE_COMMAND: str = os.getenv("HUMAN_RELEASE_COMMAND", "#BOT#")

    # Chatwoot
    CHATWOOT_API_URL: str = os.getenv("CHATWOOT_API_URL", "")
    CHATWOOT_API_KEY: str = os.getenv("CHATWOOT_API_KEY", "")
    CHATWOOT_ACCOUNT_ID: str = os.getenv("CHATWOOT_ACCOUNT_ID", "")

    # Vision (image recognition)
    VISION_ENABLED: bool = os.getenv("VISION_ENABLED", "true").lower() == "true"
    VISION_MODEL: str = os.getenv("VISION_MODEL", "gpt-4o-mini")

    # Catalog Reindex
    CATALOG_REINDEX_ENABLED: bool = os.getenv("CATALOG_REINDEX_ENABLED", "true").lower() == "true"
    CATALOG_REINDEX_INTERVAL_HOURS: int = int(os.getenv("CATALOG_REINDEX_INTERVAL_HOURS", "24"))

    # Analytics
    ANALYTICS_ENABLED: bool = os.getenv("ANALYTICS_ENABLED", "true").lower() == "true"

    # Follow-up proativo
    FOLLOW_UP_ENABLED: bool = os.getenv("FOLLOW_UP_ENABLED", "true").lower() == "true"
    FOLLOW_UP_HOURS: float = float(os.getenv("FOLLOW_UP_HOURS", "2"))
    FOLLOW_UP_MESSAGE: str = os.getenv(
        "FOLLOW_UP_MESSAGE",
        "Ficou com alguma dúvida sobre a peça? Estou aqui para ajudar! 🔧",
    )
    FOLLOW_UP_CHECK_INTERVAL_MINUTES: int = int(
        os.getenv("FOLLOW_UP_CHECK_INTERVAL_MINUTES", "30")
    )


settings = Settings()
