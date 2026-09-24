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

EVENT_MAX_TEAM_SIZE = {
    "Fixathon": 2,
    "Mute Masters": 2,
    "Treasure Titans": 2,
    "Bid Mayhem": 2,
    "QRush": 2,
    "VisionX": 1,
    "ThinkSync": 2,
    "Crazy Sell": 4,
}

REGISTRATION_STATUSES = [
    "PAYMENT_PENDING",
    "VERIFICATION_PENDING",
    "CONFIRMED",
    "REJECTED",
]

PAYMENT_STATUSES = ["PENDING", "VERIFICATION_PENDING", "SUCCESS", "REJECTED"]

# Payment statuses that lock team edits on /registerteam. PENDING (cart phase,
# proof not yet submitted) and SUCCESS (admin verified) are intentionally NOT
# locked: leaders may build a multi-event cart before paying, and may add
# students/events after verification (supplementary payment flow).
PAYMENT_LOCKED_STATUSES = ["VERIFICATION_PENDING", "REJECTED"]

PAYMENT_AUDIT_ACTIONS = [
    "CREATED",
    "PROOF_SUBMITTED",
    "VERIFIED",
    "REJECTED",
    "REOPENED",
]

CURRENCY = "INR"

ALLOWED_PROOF_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
