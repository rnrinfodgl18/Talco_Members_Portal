from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.scope import user_scope


def user(role, tannery_id=None, party_id=None):
    return SimpleNamespace(role=role, tannery_id=tannery_id, party_id=party_id)


def test_owner_cannot_change_tannery_id():
    with pytest.raises(HTTPException) as error:
        user_scope(user("member", 4), requested_tannery_id=29)
    assert error.value.status_code == 403


def test_lessee_cannot_change_party_or_tannery():
    with pytest.raises(HTTPException): user_scope(user("lessee", 4, 10), 29, 10)
    with pytest.raises(HTTPException): user_scope(user("lessee", 4, 10), 4, 11)
    assert user_scope(user("lessee", 4, 10)).party_id == 10


def test_owner_scope_keeps_all_parties_at_own_tannery():
    scope = user_scope(user("member", 4))
    assert scope.tannery_id == 4 and scope.party_id is None
