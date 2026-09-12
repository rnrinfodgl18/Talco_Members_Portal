from app.security import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("correct-horse"), hash_password("correct-horse")
    assert first != second
    assert verify_password("correct-horse", first)
    assert not verify_password("wrong-password", first)
