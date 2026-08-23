"""End-to-end payment workflow tests.

Covers: registration -> PAYMENT_PENDING -> proof upload -> VERIFICATION_PENDING
-> admin verification -> CONFIRMED, plus rejection/resubmit/reopen, UTR
duplication, amount-mismatch flagging, edit locks, idempotent resubmission,
file validation, and authorization (moderator vs Super Admin).
"""
import io
import random
import uuid

import pytest

from app.config.settings import settings


def _png_bytes(w=60, h=40) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 64, 175)).save(buf, format="PNG")
    return buf.getvalue()


def _register_leader(client, tag: str) -> tuple[str, str]:
    suffix = random.randint(100000000, 999999999)
    email = f"pay_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    college = f"PayCollege_{tag}_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/regleader",
        json={
            "name": "Payment Leader",
            "email": email,
            "mobilenumber": f"9{suffix}",
            "department": "ds",
            "college": college,
            "shift": "2",
            "password": "Passw0rd!",
            "confirmpassword": "Passw0rd!",
        },
    )
    assert r.status_code == 201, r.text
    leader_id = r.json()["userid"]
    login = client.post("/loginleader", json={"email": email, "password": "Passw0rd!"})
    assert login.status_code == 200
    return leader_id, login.json()["token"]


def _super_admin_headers(client) -> dict:
    r = client.post("/admin/adminlogin", json={"adminId": "SA1", "password": "Admin@12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_moderator_token(client) -> str:
    admin_id = f"MODP_{uuid.uuid4().hex[:6].upper()}"
    r = client.post(
        "/admin/adminreg",
        headers=_super_admin_headers(client),
        json={"adminId": admin_id, "name": "Mod", "role": 2, "password": "ModPass@123"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/admin/adminlogin", json={"adminId": admin_id, "password": "ModPass@123"})
    assert r.status_code == 200
    return r.json()["token"]


def _register_team(client, token: str, leader_id: str, event: str, count: int = 2):
    participants = [
        {
            "name": f"Student {i}",
            "registerNumber": f"PAYSTU{uuid.uuid4().hex[:8].upper()}",
            "mobile": f"9{random.randint(100000000, 999999999)}",
            "degree": "ug",
            "foodPreference": "vegetarian",
        }
        for i in range(count)
    ]
    return client.post(
        "/registerteam",
        headers={"Authorization": f"Bearer {token}"},
        json={"leaderId": leader_id, "event": event, "participants": participants},
    )


def _submit_proof(client, token: str, utr="123456789012", amount=None, filename="proof.png",
                  content=None, mime="image/png"):
    data = {}
    if utr is not None:
        data["utr"] = utr
    if amount is not None:
        data["amountPaises"] = str(amount)
    files = None
    if content is not None:
        files = {"screenshot": (filename, content, mime)}
    return client.post(
        "/payments/proof",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )


def test_full_payment_lifecycle(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "life")
    headers = {"Authorization": f"Bearer {token}"}

    r = _register_team(client, token, leader_id, "VisionX", count=2)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["uniqueStudents"] == 2
    assert body["amountDuePaises"] == 2 * fee
    assert body["currency"] == "INR"
    assert body["paymentStatus"] == "PENDING"

    mine = client.get("/payments/mine", headers=headers)
    assert mine.status_code == 200
    m = mine.json()
    assert m["data"]["paymentStatus"] == "PENDING"
    assert m["amountDuePaises"] == 2 * fee

    r = _submit_proof(client, token, amount=2 * fee, content=_png_bytes())
    assert r.status_code == 200, r.text
    assert r.json()["paymentStatus"] == "VERIFICATION_PENDING"

    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    assert all(doc["status"] == "VERIFICATION_PENDING" for doc in cands["data"])

    mod_token = _create_moderator_token(client)
    payments_list = client.get(
        "/admin/payments", headers={"Authorization": f"Bearer {mod_token}"}
    )
    assert payments_list.status_code == 403

    pending = client.get("/admin/payments?status=VERIFICATION_PENDING",
                         headers=_super_admin_headers(client))
    assert pending.status_code == 200
    target = next(p for p in pending.json()["data"] if p["leaderId"] == leader_id)
    payment_id = target["_id"]

    detail = client.get(f"/admin/payments/{payment_id}", headers=_super_admin_headers(client))
    assert detail.status_code == 200
    d = detail.json()
    assert d["data"]["expectedAmountPaises"] == 2 * fee
    assert d["data"]["submittedAmountPaises"] == 2 * fee
    actions = [a["action"] for a in d["audit"]]
    assert "CREATED" in actions and "PROOF_SUBMITTED" in actions

    proof_info = client.get(f"/admin/payments/{payment_id}/proof",
                            headers=_super_admin_headers(client))
    assert proof_info.status_code == 200
    assert proof_info.json()["url"]
    content = client.get(f"/admin/payments/{payment_id}/proof/content",
                         headers=_super_admin_headers(client))
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")

    mod_verify = client.post(f"/admin/payments/{payment_id}/verify",
                             headers={"Authorization": f"Bearer {mod_token}"})
    assert mod_verify.status_code == 403

    verify = client.post(f"/admin/payments/{payment_id}/verify",
                         headers=_super_admin_headers(client))
    assert verify.status_code == 200, verify.text
    assert verify.json()["paymentStatus"] == "SUCCESS"

    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    assert len(cands["data"]) > 0
    assert all(doc["status"] == "CONFIRMED" for doc in cands["data"])

    again = _submit_proof(client, token, amount=fee, content=_png_bytes())
    assert again.status_code == 409

    reverify = client.post(f"/admin/payments/{payment_id}/verify",
                           headers=_super_admin_headers(client))
    assert reverify.status_code == 409


def test_proof_validation_errors(client):
    leader_id, token = _register_leader(client, "val")
    r = _submit_proof(client, token, amount=100, content=_png_bytes())
    assert r.status_code == 404  # no team registered yet -> no payment row

    team = _register_team(client, token, leader_id, "QRush", count=1)
    assert team.status_code == 200

    r = _submit_proof(client, token, utr=None, amount=100, content=_png_bytes())
    assert r.status_code == 400 and "UTR" in r.json()["message"]

    r = _submit_proof(client, token, utr="   ", amount=100, content=_png_bytes())
    assert r.status_code == 400

    r = _submit_proof(client, token, utr="bad utr!", amount=100, content=_png_bytes())
    assert r.status_code == 400

    r = client.post(
        "/payments/proof",
        headers={"Authorization": f"Bearer {token}"},
        data={"utr": "123456789012"},
        files={"screenshot": ("proof.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 400  # missing amount

    r = _submit_proof(client, token, amount=100,
                      filename="notes.txt", content=b"not an image at all", mime="text/plain")
    assert r.status_code == 400 and "Unsupported file type" in r.json()["message"]

    r = _submit_proof(client, token, amount=100,
                      content=b"x" * (settings.PROOF_MAX_MB * 1024 * 1024 + 1))
    assert r.status_code == 400 and "smaller" in r.json()["message"]

    unauth = client.get("/payments/mine")
    assert unauth.status_code == 401


def test_duplicate_utr_across_leaders(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    l1, t1 = _register_leader(client, "dup1")
    l2, t2 = _register_leader(client, "dup2")
    assert _register_team(client, t1, l1, "Fixathon", count=1).status_code == 200
    assert _register_team(client, t2, l2, "Fixathon", count=1).status_code == 200

    shared = f"DUPUTR{uuid.uuid4().hex[:8].upper()}"
    r1 = _submit_proof(client, t1, utr=shared, amount=fee, content=_png_bytes())
    assert r1.status_code == 200
    r2 = _submit_proof(client, t2, utr=shared, amount=fee, content=_png_bytes())
    assert r2.status_code == 409


def test_amount_mismatch_goes_to_manual_review(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "mis")
    assert _register_team(client, token, leader_id, "Mute Masters", count=1).status_code == 200

    r = _submit_proof(client, token, amount=fee - 5000, content=_png_bytes())
    assert r.status_code == 200
    assert r.json()["paymentStatus"] == "VERIFICATION_PENDING"

    mine = client.get("/payments/mine", headers={"Authorization": f"Bearer {token}"}).json()
    assert mine["data"]["submittedAmountPaises"] == fee - 5000
    assert mine["data"]["submittedAmountPaises"] != mine["data"]["expectedAmountPaises"]

    sa = _super_admin_headers(client)
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    target = next(p for p in listed["data"] if p["leaderId"] == leader_id)
    assert target["expectedAmountPaises"] != target["submittedAmountPaises"]

    # Admin must decide: rejection works even on mismatched amounts.
    r = client.post(f"/admin/payments/{target['_id']}/verify", headers=sa)
    assert r.status_code == 200  # admin chose to accept despite mismatch


def test_reject_resubmit_and_invalid_transitions(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "rej")
    headers = {"Authorization": f"Bearer {token}"}
    assert _register_team(client, token, leader_id, "ThinkSync", count=1).status_code == 200
    assert _submit_proof(client, token, amount=fee, content=_png_bytes()).status_code == 200

    sa = _super_admin_headers(client)
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    target = next(p for p in listed["data"] if p["leaderId"] == leader_id)
    pid = target["_id"]

    r = client.post(f"/admin/payments/{pid}/reject", headers=sa, json={})
    assert r.status_code == 400 and "reason" in r.json()["message"].lower()

    r = client.post(f"/admin/payments/{pid}/reject", headers=sa,
                    json={"reason": "Screenshot unreadable"})
    assert r.status_code == 200 and r.json()["paymentStatus"] == "REJECTED"

    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    assert all(doc["status"] == "PAYMENT_PENDING" for doc in cands["data"])

    # Verify on a rejected payment is an invalid transition.
    r = client.post(f"/admin/payments/{pid}/verify", headers=sa)
    assert r.status_code == 409

    # Resubmit after rejection succeeds (new UTR to avoid dup).
    r = _submit_proof(client, token, utr=f"RESUBMIT{uuid.uuid4().hex[:4].upper()}",
                      amount=fee, content=_png_bytes())
    assert r.status_code == 200 and r.json()["paymentStatus"] == "VERIFICATION_PENDING"

    # Idempotent resubmission of the SAME utr while pending.
    mine = client.get("/payments/mine", headers=headers).json()
    same = _submit_proof(client, token, utr=mine["data"]["utr"], amount=fee,
                         content=_png_bytes())
    assert same.status_code == 200


def test_edit_lock_after_proof_submission(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "lock")
    assert _register_team(client, token, leader_id, "Treasure Titans", count=1).status_code == 200
    assert _submit_proof(client, token, amount=fee, content=_png_bytes()).status_code == 200

    r = _register_team(client, token, leader_id, "Fixathon", count=1)
    assert r.status_code == 409 and "locked" in r.json()["message"].lower()


def test_reopen_rejected_payment_super_admin_only(client):
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "ro")
    assert _register_team(client, token, leader_id, "Crazy Sell", count=1).status_code == 200
    assert _submit_proof(client, token, amount=fee, content=_png_bytes()).status_code == 200

    sa = _super_admin_headers(client)
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    pid = next(p for p in listed["data"] if p["leaderId"] == leader_id)["_id"]

    assert client.post(f"/admin/payments/{pid}/reject", headers=sa,
                       json={"reason": "wrong slot screenshot"}).status_code == 200

    mod_token = _create_moderator_token(client)
    r = client.post(f"/admin/payments/{pid}/reopen",
                    headers={"Authorization": f"Bearer {mod_token}"})
    assert r.status_code == 403

    r = client.post(f"/admin/payments/{pid}/reopen", headers=sa)
    assert r.status_code == 200 and r.json()["paymentStatus"] == "VERIFICATION_PENDING"

    audit = client.get(f"/admin/payments/{pid}", headers=sa).json()["audit"]
    actions = [a["action"] for a in audit]
    assert actions[-1] == "REOPENED"


def test_invalid_status_filter(client):
    r = client.get("/admin/payments?status=BANANA", headers=_super_admin_headers(client))
    assert r.status_code == 400
