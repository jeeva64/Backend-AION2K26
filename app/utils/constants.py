DEPARTMENTS = ["cs", "it", "ai", "ds", "ca"]
DEGREES = ["ug", "pg"]
SLOTS = ["1", "2", "BOTH"]
SHIFTS = ["1", "2"]
FOOD_PREFERENCES = ["vegetarian", "non-vegetarian"]

EVENT_SLOT_MAP = {
    "Fixathon": "1",
    "Mute Masters": "1",
    "Treasure Titans": "1",
    "Bid Mayhem": "BOTH",
    "QRush": "2",
    "VisionX": "2",
    "ThinkSync": "2",
    "Crazy Sell": "2",
}

EVENTS = [
    "Fixathon",
    "Mute Masters",
    "Treasure Titans",
    "VisionX",
    "QRush",
    "ThinkSync",
    "Bid Mayhem",
    "Crazy Sell",
]

MAX_STUDENTS_PER_LEADER = 15

REGISTRATION_STATUSES = [
    "PAYMENT_PENDING",
    "VERIFICATION_PENDING",
    "CONFIRMED",
    "REJECTED",
]

PAYMENT_STATUSES = ["PENDING", "VERIFICATION_PENDING", "SUCCESS", "REJECTED"]

PAYMENT_AUDIT_ACTIONS = [
    "CREATED",
    "PROOF_SUBMITTED",
    "VERIFIED",
    "REJECTED",
    "REOPENED",
]

CURRENCY = "INR"

PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")

ALLOWED_PROOF_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
