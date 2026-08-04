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

    Mirrors the env var names used by the original Django ``autoweb.settings``
    module (and the kustomize manifests that populate them), so existing
    deployment configs keep working unchanged.
    """

    DEBUG: bool = _bool_env("DEBUG", True)

    ALLOWED_HOSTS: list[str] = (
        ["*"]
        if os.environ.get("ALLOWED_HOSTS") is None
        else os.environ["ALLOWED_HOSTS"].split(",")
    )

    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost")
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:4200", FRONTEND_URL]

    # Database: local sqlite file, async via aiosqlite (same file the Django
    # backend used to create at BASE_DIR/db.sqlite3)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'db.sqlite3'}"
    )

    MEDIA_ROOT: Path = BASE_DIR / "models"
    MODELS_DIR: str = "pre/"
    TRAINED_MODELS_DIR: str = "trained/"
    # Bug fix: the Django backend referenced settings.DEVICES_ROOT and
    # settings.TFLITE_PARSED_MODELS_DIR (automl/serializers.py,
    # automl/views/iot_devices.py) but never defined them anywhere, so any
    # IoT device creation or IoT model deployment crashed with
    # AttributeError. Defined here for real.
    DEVICES_ROOT: Path = BASE_DIR / "models" / "devices"
    TFLITE_PARSED_MODELS_DIR: str = "tflite/"

    BOOTSTRAP_SERVERS: str | None = os.environ.get("BOOTSTRAP_SERVERS")
    CONTROL_TOPIC: str | None = os.environ.get("CONTROL_TOPIC")

    TENSORFLOW_TRAINING_MODEL_IMAGE: str | None = os.environ.get(
        "TENSORFLOW_TRAINING_MODEL_IMAGE"
    )
    TENSORFLOW_INFERENCE_MODEL_IMAGE: str | None = os.environ.get(
        "TENSORFLOW_INFERENCE_MODEL_IMAGE"
    )
    PYTORCH_TRAINING_MODEL_IMAGE: str | None = os.environ.get(
        "PYTORCH_TRAINING_MODEL_IMAGE"
    )
    PYTORCH_INFERENCE_MODEL_IMAGE: str | None = os.environ.get(
        "PYTORCH_INFERENCE_MODEL_IMAGE"
    )

    MODEL_LOGGER_TOPIC: str = os.environ.get(
        "MODEL_LOGGER_TOPIC", "FEDERATED_MODEL_CONTROL_TOPIC"
    )

    TENSORFLOW_EXECUTOR_URL: str = os.environ.get(
        "TFEXECUTOR_URL", "http://localhost:8001/"
    )
    PYTORCH_EXECUTOR_URL: str = os.environ.get(
        "PTHEXECUTOR_URL", "http://localhost:8002/"
    )

    KUBE_NAMESPACE: str = os.environ.get("KUBE_NAMESPACE", "kafkaml")
    KUBE_TOKEN: str | None = os.environ.get("KUBE_TOKEN")
    KUBE_HOST: str | None = os.environ.get("KUBE_HOST")

    BACKEND_URL: str | None = os.environ.get("BACKEND_URL")

    ENABLE_FEDML_BLOCKCHAIN: bool = _bool_env("ENABLE_FEDML_BLOCKCHAIN", False)
    FEDML_BLOCKCHAIN_TOKEN_NAME: str = os.environ.get(
        "FEDML_BLOCKCHAIN_TOKEN_NAME", "KafkaML Token"
    )
    FEDML_BLOCKCHAIN_TOKEN_SYMBOL: str = os.environ.get(
        "FEDML_BLOCKCHAIN_TOKEN_SYMBOL", "KML"
    )
    FEDML_BLOCKCHAIN_RPC_URL: str = os.environ.get(
        "FEDML_BLOCKCHAIN_RPC_URL", "http://localhost:8545"
    )
    FEDML_BLOCKCHAIN_CHAIN_ID: int = int(os.environ.get("FEDML_BLOCKCHAIN_CHAIN_ID", 1337))
    FEDML_BLOCKCHAIN_WALLET_ADDRESS: str | None = os.environ.get(
        "FEDML_BLOCKCHAIN_WALLET_ADDRESS"
    )
    FEDML_BLOCKCHAIN_WALLET_KEY: str | None = os.environ.get("FEDML_BLOCKCHAIN_WALLET_KEY")


settings = Settings()
