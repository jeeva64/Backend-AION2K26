from datetime import date, datetime

from bson import ObjectId


def sanitize(value):
    """Recursively convert MongoDB BSON types to JSON-serializable Python values."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item) for item in value]
    return value
