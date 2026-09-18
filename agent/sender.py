import logging

import httpx

logger = logging.getLogger(__name__)


def send_metrics(client: httpx.Client, payload: dict) -> bool:
    try:
        response = client.post("api/v1/metrics", json=payload)
    except httpx.RequestError as error:
        # Не выводим headers, URL или тело ответа: там могут быть секреты.
        logger.warning("Ошибка связи (%s); следующая попытка в следующем цикле", type(error).__name__)
        return False

    if response.status_code != 201:
        if response.status_code in {401, 403}:
            logger.error("HTTP %s: проверьте AGENT_TOKEN на агенте и сервере", response.status_code)
        elif response.status_code == 422:
            logger.error("HTTP 422: сервер отклонил формат или значения метрик")
        else:
            logger.warning("Сервер не подтвердил сохранение: HTTP %s", response.status_code)
        return False

    logger.info("Метрики отправлены: agent=%s cpu=%.1f%%", payload["agent_id"], payload["cpu_percent"])
    return True
