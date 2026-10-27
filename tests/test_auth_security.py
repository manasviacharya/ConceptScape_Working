"""Regression coverage for password hashing with the declared bcrypt stack."""

from auth.security import hash_password, verify_password


def test_password_hash_round_trip():
    password = "AuditOnly123!"
    hashed = hash_password(password)
    assert hashed.startswith("$2")
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)
