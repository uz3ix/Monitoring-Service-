"""Проверка служб Windows по точным системным именам; только чтение."""
import psutil


def collect_services(names: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for name in names:
        if not hasattr(psutil, "win_service_get"):
            result[name] = "unsupported"
            continue
        try:
            result[name] = psutil.win_service_get(name).status()
        except psutil.NoSuchProcess:
            result[name] = "not_found"
        except psutil.AccessDenied:
            result[name] = "access_denied"
        except (psutil.Error, OSError):
            result[name] = "unknown"
    return result


def list_services(query: str = "") -> list[dict[str, str]]:
    if not hasattr(psutil, "win_service_iter"):
        raise ValueError("Поиск служб поддерживается только на Windows")
    found = []
    for service in psutil.win_service_iter():
        name, display_name = service.name(), service.display_name()
        if query.casefold() in name.casefold() or query.casefold() in display_name.casefold():
            found.append({"name": name, "display_name": display_name})
    return sorted(found, key=lambda item: item["name"].casefold())
