import pytest
from django.core.exceptions import ValidationError

from registers import numbers
from registers.models import Lookup, RegisterBody, Registration
from tests.factories import make_employee

pytestmark = pytest.mark.django_db


def test_the_four_bodies_are_seeded_without_titles_and_unverified():
    by = {b.code: b for b in RegisterBody.objects.all()}
    assert set(by) == {"gmc", "mpl_wales", "nmc", "gphc"}
    assert [b.code for b in RegisterBody.objects.order_by("display_order")] == ["gmc", "mpl_wales", "nmc", "gphc"]
    assert by["mpl_wales"].name == "Welsh medical performers list"
    assert all(b.active and not b.verified and not b.paused and b.positions.count() == 0 for b in by.values())


@pytest.mark.parametrize("code,value,expected", [
    ("gmc", " 1234567 ", "1234567"),
    ("mpl_wales", "1234567", "1234567"),
    ("nmc", "12a 3456 b", "12A3456B"),
    ("gphc", "2012345", "2012345"),
])
def test_numbers_are_normalised_before_the_format_is_checked(code, value, expected):
    assert numbers.normalise(value) == expected
    numbers.check(code, numbers.normalise(value))      # no error


@pytest.mark.parametrize("code,value,words", [
    ("gmc", "123456", "seven digits"),
    ("gmc", "12345678", "seven digits"),
    ("gmc", "123456A", "seven digits"),
    ("nmc", "AB12C3456", "two digits, a letter, four digits and a letter"),
    ("nmc", "12A3456", "two digits, a letter, four digits and a letter"),
    ("gphc", "201234", "seven digits"),
])
def test_a_number_in_the_wrong_format_is_refused_with_the_format_in_words(code, value, words):
    with pytest.raises(ValidationError) as exc:
        numbers.check(code, value)
    assert words in str(exc.value)


def test_the_welsh_list_shares_the_gmc_number():
    assert numbers.SHARES_NUMBER_WITH == {"mpl_wales": "gmc"}
    assert numbers.FORMATS["mpl_wales"] == numbers.FORMATS["gmc"]


def test_a_registration_is_one_per_person_per_body_and_a_lookup_cascades():
    from django.db import IntegrityError
    from django.utils import timezone
    e = make_employee()
    gmc = RegisterBody.objects.get(code="gmc")
    r = Registration.objects.create(employee=e, body=gmc, number="1234567", next_check_on=timezone.localdate())
    Lookup.objects.create(registration=r, trigger=Lookup.Trigger.SCHEDULED, outcome=Lookup.Outcome.CLEAR)
    with pytest.raises(IntegrityError):
        Registration.objects.create(employee=e, body=gmc, number="7654321", next_check_on=timezone.localdate())


def test_deleting_a_registration_removes_its_lookups():
    from django.utils import timezone
    e = make_employee()
    r = Registration.objects.create(employee=e, body=RegisterBody.objects.get(code="nmc"), number="12A3456B",
                                    next_check_on=timezone.localdate())
    Lookup.objects.create(registration=r, trigger=Lookup.Trigger.ON_DEMAND, outcome=Lookup.Outcome.UNREADABLE,
                          error="FetchError")
    r.delete()
    assert Lookup.objects.count() == 0


def test_admin_lists_render_and_bodies_cannot_be_deleted_or_added(admin_client):
    gmc = RegisterBody.objects.get(code="gmc")
    assert admin_client.get("/admin/registers/registerbody/").status_code == 200
    assert admin_client.get(f"/admin/registers/registerbody/{gmc.pk}/change/").status_code == 200
    assert admin_client.get("/admin/registers/registerbody/add/").status_code == 403
    assert admin_client.post(f"/admin/registers/registerbody/{gmc.pk}/delete/").status_code == 403
    assert admin_client.get("/admin/registers/lookup/").status_code == 200
    assert admin_client.get("/admin/registers/lookup/add/").status_code == 403


def test_the_body_page_shows_verified_and_paused_read_only(admin_client):
    gmc = RegisterBody.objects.get(code="gmc")
    body = admin_client.get(f"/admin/registers/registerbody/{gmc.pk}/change/").content.decode()
    assert "Verified" in body and "Paused" in body
    assert 'name="verified"' not in body and 'name="paused_at"' not in body


def test_unpause_is_an_action_on_the_body(admin_client):
    from django.utils import timezone
    gmc = RegisterBody.objects.get(code="gmc")
    gmc.paused_at = timezone.now()
    gmc.save()
    r = admin_client.post(f"/admin/registers/registerbody/{gmc.pk}/unpause/")
    assert r.status_code == 302
    gmc.refresh_from_db()
    assert gmc.paused_at is None


def test_the_sidebar_lists_bodies_and_lookups_under_compliance(admin_client):
    body = admin_client.get("/admin/").content.decode()
    assert "Register bodies" in body and "Registration lookups" in body
