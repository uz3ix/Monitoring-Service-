from datetime import datetime, timezone
import time
from threading import Event

import psutil

from agent.config import Settings
from agent.services import collect_services


def read_counters(reader) -> dict | None:
    try:
        return reader() or None
    except (OSError, psutil.Error):
        return None


def counter_rate(before: dict | None, after: dict | None, field: str, elapsed: float) -> float | None:
    # Изменение набора устройств или сброс счётчиков — пробел в данных, не ноль.
    if not before or not after or before.keys() != after.keys() or elapsed <= 0:
        return None
    deltas = [getattr(after[key], field) - getattr(before[key], field) for key in before]
    if any(delta < 0 for delta in deltas):
        return None
    return sum(deltas) / elapsed


def collect_metrics(settings: Settings, sample_seconds: float = 1, stop: Event | None = None) -> dict | None:
    stop = stop if stop is not None else Event()
    network_before = read_counters(lambda: psutil.net_io_counters(pernic=True))
    disk_before = read_counters(lambda: psutil.disk_io_counters(perdisk=True))
    psutil.cpu_percent(interval=None)  # Первый неблокирующий вызов — начало замера.
    started = previous = time.monotonic()
    weighted_cpu = 0.0
    cpu_max = 0.0
    elapsed = 0.0
    while elapsed < sample_seconds:
        if stop.wait(min(1.0, sample_seconds - elapsed)):
            return None
        cpu = psutil.cpu_percent(interval=None)
        now = time.monotonic()
        weighted_cpu += cpu * (now - previous)
        cpu_max = max(cpu_max, cpu)
        previous = now
        elapsed = now - started

    network_after = read_counters(lambda: psutil.net_io_counters(pernic=True))
    disk_after = read_counters(lambda: psutil.disk_io_counters(perdisk=True))
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(settings.disk_path)
    return {
        "agent_id": settings.agent_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": weighted_cpu / elapsed,
        "cpu_max_percent": cpu_max,
        "sample_duration_seconds": elapsed,
        "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
        "network_receive_bytes_per_second": counter_rate(network_before, network_after, "bytes_recv", elapsed),
        "network_send_bytes_per_second": counter_rate(network_before, network_after, "bytes_sent", elapsed),
        "disk_read_bytes_per_second": counter_rate(disk_before, disk_after, "read_bytes", elapsed),
        "disk_write_bytes_per_second": counter_rate(disk_before, disk_after, "write_bytes", elapsed),
        "services": collect_services(settings.services),
        "memory_used_bytes": memory.used,
        "memory_total_bytes": memory.total,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
    }
