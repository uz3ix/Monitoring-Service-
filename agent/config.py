import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

DEFAULT_ENV = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class Settings:
    server_url: str
    agent_id: str
    token: str = field(repr=False)
    disk_path: str
    interval: float
    timeout: float
    services: tuple[str, ...] = ()


def load_settings(env_file: Path = DEFAULT_ENV) -> Settings:
    # Переменные окружения приоритетнее .env. База данных агенту не нужна.
    values = {**dotenv_values(env_file), **os.environ}

    def positive_number(name: str, default: str, minimum: float) -> float:
        try:
            value = float(values.get(name, default))
        except (TypeError, ValueError):
            raise ValueError(f"{name}: ожидается число") from None
        if not math.isfinite(value) or value < minimum:
            raise ValueError(f"{name}: значение должно быть не меньше {minimum}")
        return value

    server_url = (values.get("SERVER_URL") or "http://127.0.0.1:8000").rstrip("/")
    try:
        parsed = urlsplit(server_url)
        port = parsed.port
        valid_url = (
            parsed.scheme in {"http", "https"} and parsed.hostname
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and (port is None or port > 0)
            and not any(char.isspace() for char in server_url)
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("SERVER_URL: нужен HTTP(S)-адрес без логина, пароля, query и fragment")

    agent_id = values.get("AGENT_ID") or ""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", agent_id):
        raise ValueError("AGENT_ID: 1–128 латинских букв, цифр, точек, дефисов или подчёркиваний; первый символ — буква или цифра")

    token = values.get("AGENT_TOKEN") or ""
    if not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ValueError("AGENT_TOKEN: задайте непустой токен из печатных ASCII-символов без пробелов")

    disk_path = values.get("DISK_PATH") or Path.cwd().anchor
    if not Path(disk_path).is_absolute() or not Path(disk_path).is_dir():
        raise ValueError("DISK_PATH: нужен существующий абсолютный путь к папке на наблюдаемом диске")

    services = tuple(dict.fromkeys(name.strip() for name in (values.get("MONITOR_SERVICES") or "").split(",") if name.strip()))
    if len(services) > 50 or any(len(name) > 256 or any(ord(char) < 32 for char in name) for name in services):
        raise ValueError("MONITOR_SERVICES: не более 50 имён служб, до 256 символов каждое")

    return Settings(
        server_url=server_url,
        agent_id=agent_id,
        token=token,
        disk_path=disk_path,
        interval=positive_number("AGENT_INTERVAL_SECONDS", "60", 1),
        timeout=positive_number("AGENT_TIMEOUT_SECONDS", "5", 0.1),
        services=services,
    )
