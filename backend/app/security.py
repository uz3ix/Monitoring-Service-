import os
import secrets
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key = APIKeyHeader(name="X-Agent-Token", auto_error=False)


def require_agent_token(token: Annotated[str | None, Security(api_key)]) -> None:
    expected = os.getenv("AGENT_TOKEN", "")
    if not expected.strip():
        raise HTTPException(status_code=503, detail="AGENT_TOKEN не настроен на сервере")
    if token is None or not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий токен агента")
