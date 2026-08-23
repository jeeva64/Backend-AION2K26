"""End-to-end API tests covering every migrated route.

Requires a running PostgreSQL at localhost:5432 (role aion/aion). The suite
targets its own database (aion_pytest_test) which is dropped and rebuilt via
`alembic upgrade head` by the session fixture in conftest.py.
"""

import pytest


def test_full_flow(client):
    assert client.get("/health").status_code == 200

    r = client.post("/admin/adminlogin", json={"adminId": "SA1", "password": "Admin@12345"})
    assert r.status_code == 200 and r.json().get("token")
    admin_token = r.json()["token"]
    h = {"Authorization": f"Bearer {admin_token}"}

    r = client.post("/admin/adminlogin", json={"adminId": "SA1", "password": "wrong"})
    assert r.status_code == 401

    r = client.post("/admin/adminreg", json={"adminId": "MOD1", "name": "Moderator", "role": 2, "password": "Admin@12345"})
    assert r.status_code == 401

    r = client.post("/admin/adminreg", headers=h, json={"adminId": "MOD1", "name": "Moderator", "role": 2, "password": "Admin@12345"})
    assert r.status_code == 201

    r = client.post("/admin/adminreg", headers=h, json={"adminId": "MOD1", "name": "Moderator", "role": 2, "password": "Admin@12345"})
    assert r.status_code == 400

    r = client.post("/admin/adminreg", headers=h, json={"adminId": "MOD2", "name": "M", "role": 3, "password": "Admin@12345"})
    assert r.status_code == 400

    colleges = [
        {"collegeId": "C001", "name": "Anna University", "state": "TN", "district": "Chennai"},
        {"collegeId": "C002", "name": "SRM Institute", "state": "TN", "district": "Chengalpattu"},
    ]
    r = client.post("/addcollege", headers=h, json=colleges)
    assert r.status_code == 201 and r.json().get("count") == 2

    r = client.post("/addcollege", json=colleges)
    assert r.status_code == 401

    r = client.get("/getcollege")
    assert r.status_code == 200 and len(r.json()["data"]) == 2

    r = client.post(
        "/regleader",
        json={
            "name": "Arjun Kumar",
            "email": "Arjun@Example.com",
            "mobilenumber": 9876543210,
            "department": "cs",
            "college": "Anna University",
            "shift": "1",
            "password": "Passw0rd!",
            "confirmpassword": "Passw0rd!",
        },
    )
    assert r.status_code == 201 and r.json().get("userid", "").startswith("LD")
    leader_id = r.json()["userid"]

    r = client.post(
        "/regleader",
        json={
            "name": "Duplicate",
            "email": "arjun@example.com",
            "mobilenumber": 9999999999,
            "department": "it",
            "college": "SRM Institute",
            "shift": "2",
            "password": "Passw0rd!",
            "confirmpassword": "Passw0rd!",
        },
    )
    assert r.status_code == 400

    r = client.post(
        "/regleader",
        json={
            "name": "BadDept",
            "email": "bad@example.com",
            "mobilenumber": 9999999999,
            "department": "mech",
            "college": "SRM Institute",
            "shift": "2",
            "password": "Passw0rd!",
            "confirmpassword": "Passw0rd!",
        },
    )
    assert r.status_code == 400

    r = client.post("/loginleader", json={"email": "  arjun@example.com ", "password": "Passw0rd!"})
    assert r.status_code == 200 and r.json().get("token")
    leader_token = r.json()["token"]
    lh = {"Authorization": f"Bearer {leader_token}"}

    r = client.post("/loginleader", json={"email": "arjun@example.com", "password": "wrong"})
    assert r.status_code == 401

    participants = [
        {"name": "Student One", "registerNumber": "ra2111003010101", "mobile": 9123456789, "degree": "ug", "foodPreference": "vegetarian"},
        {"name": "Student Two", "registerNumber": "ra2111003010102", "mobile": 9234567890, "degree": "pg", "foodPreference": "non-vegetarian"},
    ]
    r = client.post("/registerteam", headers=lh, json={"leaderId": leader_id, "event": "Fixathon", "participants": participants})
    assert r.status_code == 200 and r.json().get("created") == 2

    r = client.post("/registerteam", headers=lh, json={"leaderId": leader_id, "event": "Fixathon", "participants": participants})
    assert r.status_code == 409

    r = client.post("/registerteam", json={"leaderId": leader_id, "event": "QRush", "participants": participants})
    assert r.status_code == 401

    r = client.post(
        "/registerteam",
        headers=lh,
        json={
            "leaderId": leader_id,
            "event": "QRush",
            "participants": [{"name": "Brand New", "registerNumber": "ra2111003010909", "mobile": "9345678901", "degree": "ug"}],
        },
    )
    assert r.status_code == 400

    r = client.post("/registerteam", headers=lh, json={"leaderId": "LD999", "event": "QRush", "participants": participants})
    assert r.status_code == 403

    r = client.post("/getcandidates", headers=lh, json={"user_id": leader_id})
    assert r.status_code == 200 and r.json()["totalStudents"] == 2

    r = client.get(f"/stats/{leader_id}", headers=lh)
    assert r.status_code == 200 and r.json()["stats"]["totalStudents"] == 2

    r = client.get("/stats/LD999", headers=lh)
    assert r.status_code == 403

    r = client.post("/admin/viewteam", headers=h, json={"college": "Anna University", "department": "cs"})
    assert r.status_code == 200 and len(r.json()["data"]) == 2

    r = client.post("/admin/vieweventregs", headers=h, json={"eventName": "Fixathon"})
    assert r.status_code == 200 and r.json()["totalTeams"] == 1

    r = client.post("/admin/vieweventregs", headers=h, json={"eventName": "Nope"})
    assert r.status_code == 404

    r = client.get("/admin/dashboardstats", headers=h)
    assert r.status_code == 200
    stats = r.json()["stats"]
    assert stats["totalMembers"] == 2 and stats["totalTeams"] == 1
    assert stats["vegCount"] == 1 and stats["nonVegCount"] == 1

    r = client.post("/admin/vieweventregs", headers=h, json={"eventName": "Bid Mayhem"})
    assert r.status_code == 404

    r = client.get(f"/stats/{leader_id}", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401

    second_event_participants = [
        {"name": "Student Two", "registerNumber": "ra2111003010102", "mobile": "9234567890", "degree": "pg"}
    ]
    r = client.post("/registerteam", headers=lh, json={"leaderId": leader_id, "event": "QRush", "participants": second_event_participants})
    assert r.status_code == 200 and r.json().get("updated") == 1

    r = client.post(
        "/registerteam",
        headers=lh,
        json={
            "leaderId": leader_id,
            "event": "Bid Mayhem",
            "participants": [{"name": "Student One", "registerNumber": "ra2111003010101", "mobile": "9123456789", "degree": "ug", "foodPreference": "vegetarian"}],
        },
    )
    assert r.status_code == 409

    r = client.post(
        "/regleader",
        json={
            "name": "Kavya Sri",
            "email": "kavya@example.com",
            "mobilenumber": 8112345678,
            "department": "ai",
            "college": "SRM Institute",
            "shift": "2",
            "password": "Passw0rd!",
            "confirmpassword": "Passw0rd!",
        },
    )
    assert r.status_code == 201
    leader2_id = r.json()["userid"]

    r = client.post("/loginleader", json={"email": "kavya@example.com", "password": "Passw0rd!"})
    leader2_token = r.json()["token"]
    lh2 = {"Authorization": f"Bearer {leader2_token}"}

    r = client.post(
        "/registerteam",
        headers=lh2,
        json={
            "leaderId": leader2_id,
            "event": "Bid Mayhem",
            "participants": [{"name": "BM Student", "registerNumber": "ra2111003020202", "mobile": "9012345678", "degree": "ug", "foodPreference": "non-vegetarian"}],
        },
    )
    assert r.status_code == 200 and r.json().get("created") == 1

    r = client.post(
        "/registerteam",
        headers=lh2,
        json={
            "leaderId": leader2_id,
            "event": "Fixathon",
            "participants": [{"name": "BM Student", "registerNumber": "ra2111003020202", "mobile": "9012345678", "degree": "ug", "foodPreference": "non-vegetarian"}],
        },
    )
    assert r.status_code == 409

    r = client.delete(f"/admin/deleteteambyevent/{leader2_id}/Bid%20Mayhem", headers=h)
    assert r.status_code == 200 and r.json().get("deletedCount") == 1

    r = client.delete(f"/admin/deleteteambyevent/{leader_id}/QRush", headers=h)
    assert r.status_code == 200 and r.json().get("updatedCount") == 1

    r = client.delete(f"/admin/deleteteambyevent/{leader_id}/Fixathon", headers=h)
    assert r.status_code == 200 and r.json().get("deletedCount") == 2

    r = client.delete(f"/admin/deleteteam/{leader_id}", headers=h)
    assert r.status_code == 404

    r = client.delete(f"/admin/deleteteam/{leader_id}")
    assert r.status_code == 401


def test_auth_matrix_leader(client):
    r = client.post("/getcandidates", json={"user_id": "LDx"})
    assert r.status_code == 401
    r = client.get("/stats/LDx")
    assert r.status_code == 401
    r = client.post("/registerteam", json={"leaderId": "LDx", "event": "Fixathon", "participants": []})
    assert r.status_code == 401


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert r.headers.get("strict-transport-security")
    assert r.headers.get("x-request-id")
