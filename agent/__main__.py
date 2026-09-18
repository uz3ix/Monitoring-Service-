import argparse
import logging
import signal
import time
from pathlib import Path
from threading import Event

import httpx
import psutil

from agent.collector import collect_metrics
from agent.config import DEFAULT_ENV, Settings, load_settings
from agent.sender import send_metrics
from agent.services import list_services

logger = logging.getLogger(__name__)


def run_cycle(settings: Settings, client: httpx.Client, sample_seconds: float = 1, stop: Event | None = None) -> bool:
    try:
        payload = collect_metrics(settings, sample_seconds=sample_seconds, stop=stop)
    except (OSError, psutil.Error):
        logger.error("Не удалось собрать метрики; проверьте доступ к DISK_PATH")
        return False
    return send_metrics(client, payload) if payload is not None else False


def main() -> int:
    parser = argparse.ArgumentParser(description="Агент мониторинга CPU, RAM и диска")
    parser.add_argument("--once", action="store_true", help="Одно измерение и выход: 0 — успех, 1 — ошибка отправки/сбора")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV, help="Путь к .env (по умолчанию в корне проекта)")
    parser.add_argument("--list-services", nargs="?", const="", metavar="ПОИСК", help="Список служб Windows; необязательный поиск по имени и описанию")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.list_services is not None:
        try:
            for service in list_services(args.list_services):
                print(f"{service['name']}\t{service['display_name']}")
            return 0
        except (ValueError, OSError, psutil.Error):
            logger.error("Не удалось получить службы: проверьте доступ; функция поддерживается на Windows")
            return 2
    try:
        settings = load_settings(args.env_file)
    except ValueError as error:
        logger.error("Ошибка настроек: %s", error)
        return 2
    except OSError:
        logger.error("Не удалось прочитать файл настроек")
        return 2

    stop = Event()

    def request_stop(signum, frame):
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    logger.info("Агент %s запущен; интервал %.1f с", settings.agent_id, settings.interval)
    # Не следуем редиректам, чтобы не передать токен другому адресу.
    with httpx.Client(
        base_url=settings.server_url + "/",
        headers={"X-Agent-Token": settings.token},
        timeout=settings.timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        deadline = time.monotonic() + settings.interval
        while not stop.is_set():
            window = 1.0 if args.once else max(1.0, deadline - time.monotonic())
            successful = run_cycle(settings, client, sample_seconds=window, stop=stop)
            if args.once:
                return 0 if successful else 1
            deadline += settings.interval
            if deadline <= time.monotonic():
                deadline = time.monotonic() + settings.interval
            # При ошибке сбора не допускаем цикла без паузы.
            if not successful and not stop.is_set():
                stop.wait(1)

    logger.info("Агент остановлен")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
