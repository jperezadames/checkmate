"""Shared error result (contracts/interfaces.md section 1.5).

Module functions never raise to main; they return err(CODE, message) instead.
Code must only check "error"; "message" is for humans and logs.
"""


def err(code: str, message: str) -> dict:
    return {"ok": False, "error": code, "message": message}
