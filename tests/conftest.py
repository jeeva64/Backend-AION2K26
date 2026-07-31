import os

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/aion_pytest_test")
os.environ.setdefault("JWT_SECRET", "pytest-secret-key-1234567890")
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.auth.security import hash_password
from app.main import app


@pytest.fixture(scope="session")
def client():
    sync = MongoClient(os.environ["MONGO_URI"])
    db_name = sync.get_default_database().name or "aion_pytest_test"
    sync.drop_database(db_name)
    sync[db_name]["admins"].insert_one(
        {"adminId": "SA1", "name": "Root", "role": 1, "password": hash_password("Admin@12345")}
    )
    sync.close()

    with TestClient(app) as c:
        yield c
