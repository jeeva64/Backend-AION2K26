class APIError(Exception):
    """Application-level error rendered as {"success": false, "message": ...}."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)
