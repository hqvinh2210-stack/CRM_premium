from __future__ import annotations

import re


def normalize_vn_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    if digits.startswith("0") and len(digits) >= 9:
        return digits
    return digits or phone.strip()
