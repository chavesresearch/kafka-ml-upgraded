import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value == "1" or value.lower() == "true"


class Settings:
    """Application configuration, read from environment variables.

    Mirrors the env var names the original Django ``autoweb.settings``
    module used (and that the kustomize manifests already populate), so
    existing deployment configs keep working unchanged.
    """

    DEBUG: bool = _bool_env("DEBUG", True)

    ALLOWED_HOSTS: list[str] = (
        ["federated-backend", "frontend", "127.0.0.1", "localhost", "[::1]"]
        if os.environ.get("ALLOWED_HOSTS") is None
        else os.environ["ALLOWED_HOSTS"].split(",")
    )

    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost")
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:4200", FRONTEND_URL]

    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'db.sqlite3'}"
    )

    KML_CLOUD_BOOTSTRAP_SERVERS: str | None = os.environ.get("KML_CLOUD_BOOTSTRAP_SERVERS")
    FEDERATED_BOOTSTRAP_SERVERS: str | None = os.environ.get("FEDERATED_BOOTSTRAP_SERVERS")

    DATA_CONTROL_TOPIC: str | None = os.environ.get("DATA_CONTROL_TOPIC")
    MODEL_CONTROL_TOPIC: str | None = os.environ.get("MODEL_CONTROL_TOPIC")

    TENSORFLOW_FEDERATED_TRAINING_MODEL_IMAGE: str | None = os.environ.get(
        "TENSORFLOW_FEDERATED_TRAINING_MODEL_IMAGE"
    )
    PYTORCH_FEDERATED_TRAINING_MODEL_IMAGE: str | None = os.environ.get(
        "PYTORCH_FEDERATED_TRAINING_MODEL_IMAGE"
    )

    KUBE_NAMESPACE: str = os.environ.get("KUBE_NAMESPACE", "kafkaml")
    KUBE_TOKEN: str | None = os.environ.get("KUBE_TOKEN")
    KUBE_HOST: str | None = os.environ.get("KUBE_HOST")

    FEDML_BLOCKCHAIN_WALLET_ADDRESS: str | None = os.environ.get("FEDML_BLOCKCHAIN_WALLET_ADDRESS")
    FEDML_BLOCKCHAIN_WALLET_KEY: str | None = os.environ.get("FEDML_BLOCKCHAIN_WALLET_KEY")


def _validate_production_safety(s: Settings) -> None:
    """Refuse to boot with insecure defaults when ENVIRONMENT=production.

    Same rationale/pattern as ../../../backend/app/config.py's own check -
    DEBUG/ALLOWED_HOSTS fail open when unset, which is convenient locally
    but shouldn't silently apply in production.
    """
    if s.ENVIRONMENT != "production":
        return
    problems = []
    if s.DEBUG:
        problems.append("DEBUG is enabled (set DEBUG=0)")
    if problems:
        raise RuntimeError(
            "Refusing to start with ENVIRONMENT=production and insecure config: "
            + "; ".join(problems)
        )


settings = Settings()
_validate_production_safety(settings)
