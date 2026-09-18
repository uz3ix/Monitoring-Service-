# Сервис мониторинга

FastAPI с проверкой подключения к PostgreSQL, приёмом и чтением метрик.
Compose запускает только базу, бэкенд запускается отдельно на компьютере.

Агент для сбора реальных показателей CPU, RAM и диска готов:
[настройка, запуск и объяснение кода](agent/README.md).

## Настройки

Локальные параметры подключения находятся в `.env` в корне репозитория.
Файл исключён из Git. `.env.example` — шаблон с учебными значениями.
При первом запуске после клонирования, если `.env` ещё нет:

```powershell
Copy-Item .env.example .env
```

- `POSTGRES_HOST` — адрес базы для бэкенда: `127.0.0.1`.
- `POSTGRES_PORT` — порт базы на компьютере: `5432`.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — пользователь, пароль и имя базы.
- `AGENT_TOKEN` — общий токен для записи и чтения метрик через заголовок `X-Agent-Token`.
  Задайте собственное значение вместо шаблона. При отсутствии токена API метрик
  возвращает 503. Токен не указывайте в URL и не добавляйте в Git.

Compose автоматически читает `.env` рядом с `compose.yaml`.
Бэкенд читает тот же файл через python-dotenv независимо от рабочей папки.
Уже заданные переменные окружения имеют приоритет над файлом.

## Запуск на Windows

Нужны Docker Desktop в режиме Linux containers и Python 3.12 или новее.
Все команды выполняйте из корня репозитория `Monitoring-Service-`.
Запустите Docker Desktop, затем поднимите базу:

```powershell
docker compose up -d --wait db
docker compose ps
```

База доступна только с этого ПК. Если порт 5432 занят, задайте другой
`POSTGRES_PORT` в `.env`, например 5433. Внутренний порт контейнера остаётся 5432.

Создайте виртуальное окружение и установите зависимости:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Если `py` недоступна, используйте `python` вместо `py -3`.
Создайте таблицы миграцией (также выполняйте после получения новых миграций):

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Запустите бэкенд:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

- Документация: http://localhost:8000/docs
- Проверка подключения: http://localhost:8000/health

В документации раскройте `GET /health`, нажмите **Try it out**, затем **Execute**.
При работающей базе получите HTTP 200:

```json
{"status": "ok", "database": "ok"}
```

При недоступной базе API возвращает HTTP 503.
Python-код обновляется автоматически благодаря `--reload`.
После изменения `.env` перезапустите бэкенд. Настройки контейнера применяются
повторным `docker compose up -d --wait db`.

## Файлы приложения

- `backend/app/main.py` — приложение FastAPI и обработчик `GET /health`.
- `backend/app/database.py` — загрузка настроек и подключение через SQLAlchemy.
- `backend/app/models.py` — SQLAlchemy-модель таблицы `metrics`.
- `backend/app/schemas.py` — Pydantic-схемы проверки запроса и формирования ответа.
- `backend/app/routes.py` — ручки записи и чтения метрик.
- `backend/app/security.py` — проверка токена.
- `backend/migrations/` — миграции Alembic, создающие таблицы в базе.
- `backend/requirements.txt` — зависимости Python.
- `compose.yaml` — запуск PostgreSQL с настройками из `.env`.
- `backend/Dockerfile` — заготовка контейнера бэкенда на будущее. Текущий Compose
  её не использует; при контейнерном запуске настройки передаются окружением.

Путь запроса: браузер → Uvicorn → FastAPI → SQLAlchemy → PostgreSQL → JSON.
Запрос `SELECT 1` проверяет связь с базой. Таблица `metrics` хранит одну строку
на каждое измерение. `collected_at` — время сбора агентом, `received_at` — время
приёма сервером. CPU измеряется в процентах, память и выбранный диск — в байтах.

## Проверка метрик через документацию API

1. Откройте `/docs`, нажмите **Authorize**, вставьте значение `AGENT_TOKEN` из
   своего `.env` (без `AGENT_TOKEN=`), подтвердите и закройте окно.
2. В `POST /api/v1/metrics` нажмите **Try it out**, вставьте JSON и **Execute**:

```json
{
  "agent_id": "my-pc",
  "collected_at": "2026-09-18T12:00:00Z",
  "cpu_percent": 24.5,
  "memory_used_bytes": 8589934592,
  "memory_total_bytes": 17179869184,
  "disk_used_bytes": 107374182400,
  "disk_total_bytes": 536870912000
}
```

3. Ответ `201` содержит сохранённые поля, `id` и `received_at`.
4. В `GET /api/v1/agents/{agent_id}/metrics/latest` укажите `my-pc` и выполните
   запрос. Ответ `200` содержит последнее измерение по `collected_at`;
   при одинаковом времени выбирается запись с большим `id`.

Неверный или отсутствующий токен даёт `401`, отсутствие измерений — `404`,
некорректное тело запроса — `422`. Время должно содержать часовой пояс;
занятый объём не может превышать общий, CPU должен быть от 0 до 100.
Идентификатор агента: до 128 латинских букв, цифр, точек, дефисов и подчёркиваний,
начинается с буквы или цифры. Для первой версии регистрация агента не требуется.
Повторная отправка создаёт отдельную запись. Общий токен разрешает доступ ко
всем агентам — это упрощение для локального MVP.

## Автоматические проверки

На работающей PostgreSQL после применения миграций:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -r agent/requirements.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Тесты проверяют сохранение и чтение, порядок измерений, токен и валидацию.
Тестовые строки откатываются транзакцией; счётчик ID при этом может увеличиться.

## Остановка и данные

Бэкенд останавливается через Ctrl+C. Журналы базы и остановка Compose:

```powershell
docker compose logs --tail=100 db
docker compose down
```

Данные сохраняются в Docker volume между перезапусками.
Параметры пользователя, пароля и имени базы инициализируют только пустой volume.
Изменение `.env` не меняет учётные данные существующей базы — их нужно менять
отдельно в PostgreSQL. `docker compose down -v` удаляет volume со всеми данными;
используйте эту команду только для намеренного полного сброса учебной базы.

## Документация

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy и PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Миграции Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Проверка API-ключа в FastAPI](https://fastapi.tiangolo.com/reference/security/)
