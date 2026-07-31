import json

from fastapi.responses import JSONResponse


class MongoJSONResponse(JSONResponse):
    """JSONResponse that can serialize MongoDB types (ObjectId, datetime)."""

    def render(self, content) -> bytes:
        return json.dumps(content, default=str, ensure_ascii=False).encode("utf-8")
