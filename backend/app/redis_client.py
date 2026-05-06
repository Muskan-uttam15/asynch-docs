import json
from typing import Any

import redis

from app.config import settings


redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def progress_channel(document_id: int) -> str:
    return f"progress:{document_id}"


def publish_progress(document_id: int, payload: dict[str, Any]) -> None:
    redis_client.publish(progress_channel(document_id), json.dumps(payload))
