import pytest
from django.db import IntegrityError

from tests.factories import make_employee


def test_name_prefers_preferred_name(db):
    e = make_employee(preferred_name="Sammy")
    assert e.name == "Sammy Patel"
    e.preferred_name = ""
    assert e.name == "Sam Patel"


def test_work_email_unique_case_insensitive(db):
    make_employee(email="a@example.org")
    with pytest.raises(IntegrityError):
        make_employee(first="Other", email="A@example.org")


def test_str_is_name(db):
    assert str(make_employee()) == "Sam Patel"
