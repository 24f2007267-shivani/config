
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def coerce(key, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in ("true", "1", "yes", "on")

    return value


def apply_layer(config, values):
    for key, value in values.items():
        if value is None:
            continue

        key = key.lower()

        if key == "num_workers":
            key = "workers"
        elif key.startswith("app_"):
            key = key[4:]

        if key in config:
            config[key] = coerce(key, value)


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    # 1. Hardcoded defaults
    config = DEFAULTS.copy()

    # 2. Environment-specific YAML
    environment = os.getenv("APP_ENV", "development")
    yaml_file = BASE_DIR / f"config.{environment}.yaml"

    if yaml_file.exists():
        with yaml_file.open("r", encoding="utf-8") as file:
            yaml_values = yaml.safe_load(file) or {}
        apply_layer(config, yaml_values)

    # 3. .env file (read without modifying OS environment)
    env_file = dotenv_values(BASE_DIR / ".env")
    apply_layer(config, env_file)

    # 4. Actual OS environment variables (highest config-layer precedence)
    os_values = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    apply_layer(config, os_values)

    # 5. CLI-style query overrides (highest precedence overall)
    for item in set:
        key, separator, value = item.partition("=")
        if not separator:
            continue

        key = key.strip().lower()
        if key in config:
            config[key] = coerce(key, value)

    # Never expose the actual secret
    config["api_key"] = "****"

    return config