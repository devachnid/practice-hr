"""NI numbers stored before the format was enforced, and typed with spaces:
the normalising data migration, the forms' normalisation and My record
with a stale value (final review C1)."""

import importlib
from datetime import timedelta

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils import timezone

from onboarding.forms import DetailsForm
from people import ni
from people.admin_forms import EmployeeForm
from people.models import Employee
from people.services import employees, employments, positions, titles
from tests.factories import make_employee, make_employment, make_team

pytestmark = pytest.mark.django_db
migration = importlib.import_module("people.migrations.0017_normalise_ni_numbers")


def _store(employee, value):
    Employee.objects.filter(pk=employee.pk).update(
        ni_number=value
    )  # as saved before 0015


def _ni(employee):
    return Employee.objects.get(pk=employee.pk).ni_number


def test_the_migration_normalises_a_stored_lowercase_or_spaced_ni_number():
    lower, spaced, good, blank = (
        make_employee(email=f"{n}@example.com") for n in "abcd"
    )
    _store(lower, "ab123456c")
    _store(spaced, " qq12345 ")
    _store(good, "QQ123456C")
    lines = []
    changed, bad = migration.normalise_ni_numbers(apps, None, out=lines.append)
    assert changed == 1 and bad == [spaced.pk]
    assert (_ni(lower), _ni(spaced), _ni(good), _ni(blank)) == (
        "AB123456C",
        " qq12345 ",
        "QQ123456C",
        "",
    )


def test_the_migration_leaves_a_value_that_still_fails_and_reports_its_pk_only():
    wrong = make_employee(first="Quentin", last="Blake", email="wrong@example.com")
    fixable = make_employee(email="fixable@example.com")
    _store(wrong, "Q1234567")
    _store(fixable, "ab123456d")
    lines = []
    changed, bad = migration.normalise_ni_numbers(apps, None, out=lines.append)
    assert (changed, bad) == (1, [wrong.pk])
    assert _ni(wrong) == "Q1234567" and _ni(fixable) == "AB123456D"
    (line,) = lines
    assert (
        "normalised: 1" in line
        and "still not valid: 1" in line
        and f"employee pks {wrong.pk}" in line
    )
    for secret in ("Quentin", "Blake", "Q1234567", "AB123456D"):
        assert secret not in line
    assert migration.normalise_ni_numbers(apps, None, out=lines.append) == (
        0,
        [wrong.pk],
    )  # idempotent


def test_the_migration_says_nothing_when_there_is_nothing_to_report():
    lines = []
    assert migration.normalise_ni_numbers(apps, None, out=lines.append) == (0, [])
    assert lines == []


def test_the_normaliser_strips_inner_spaces_and_capitalises():
    assert ni.normalise(" ab 12 34 56 c ") == "AB123456C"
    assert ni.normalise("") == "" and ni.normalise(None) == ""
    assert migration.normalise(" ab 12 34 56 c ") == "AB123456C"


@pytest.mark.parametrize("value", ["AB123456C\n", "AB１２３４５６C", "AB123456E"])
def test_the_regex_takes_ascii_digits_only_and_nothing_after_the_end(hr_admin, value):
    e = make_employee()
    with pytest.raises(ValidationError):
        employees.update(hr_admin, e, ni_number=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("bank_sort_code", "12-34-56\n"),
        ("bank_sort_code", "１２-34-56"),
        ("bank_account_number", "1234567\n"),
        ("bank_account_number", "1234567８"),
    ],
)
def test_bank_formats_take_ascii_digits_only_and_nothing_after_the_end(
    hr_admin, field, value
):
    e = make_employee()
    with pytest.raises(ValidationError):
        employees.update(hr_admin, e, **{field: value})


def test_the_details_form_saves_a_spaced_lowercase_ni_number_in_the_stored_form(
    hr_admin, employee_user, employee_client
):
    e = make_employee(user=employee_user)
    start = timezone.localdate() + timedelta(days=10)
    emp = employments.start(hr_admin, e, start)
    positions.add(
        hr_admin, emp, titles.get_or_create("Receptionist"), make_team(), None, start
    )
    r = employee_client.post(
        "/onboarding/details/",
        {
            "ni_number": "ab 12 34 56 c",
            "contacts-TOTAL_FORMS": "0",
            "contacts-INITIAL_FORMS": "0",
            "contacts-MIN_NUM_FORMS": "0",
            "contacts-MAX_NUM_FORMS": "3",
        },
    )
    assert r.status_code == 302
    assert _ni(e) == "AB123456C"


def test_the_admin_employee_form_normalises_the_ni_number():
    e = make_employee()
    data = {
        "first_name": e.first_name,
        "last_name": e.last_name,
        "work_email": e.work_email,
        "ni_number": " ab 12 34 56 c ",
    }
    form = EmployeeForm(data, instance=Employee.objects.get(pk=e.pk))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["ni_number"] == "AB123456C"
    form = DetailsForm(
        {"ni_number": "ab 12 34 56"}, instance=Employee.objects.get(pk=e.pk)
    )
    assert (
        not form.is_valid() and "ni_number" in form.errors
    )  # still checked once normalised


def test_my_record_with_a_stale_bad_ni_number_shows_an_error_not_a_500(
    employee_user, employee_client
):
    e = make_employee(user=employee_user)
    make_employment(employee=e)
    _store(e, "Q1234567")
    r = employee_client.post(
        "/people/me/",
        {
            "phone": "0113 496 0000",
            "personal_email": "",
            "address_line1": "",
            "address_line2": "",
            "town": "",
            "postcode": "",
        },
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "NI number: Enter the NI number" in body and "Ask HR to correct it." in body
    assert Employee.objects.get(pk=e.pk).phone == ""  # nothing saved


def test_a_whitespace_only_ni_number_becomes_blank_and_is_not_reported():
    e = make_employee(email="ws@example.com")
    _store(e, "   ")
    lines = []
    assert migration.normalise_ni_numbers(apps, None, out=lines.append) == (1, [])
    assert _ni(e) == ""
    assert lines == ["\n  NI numbers normalised: 1; still not valid: 0"]


@pytest.mark.parametrize(
    "field,valid",
    [
        ("ni_number", "AB123456C"),
        ("bank_sort_code", "12-34-56"),
        ("bank_account_number", "12345678"),
    ],
)
def test_the_format_validators_refuse_a_trailing_newline(field, valid):
    """The RegexValidator itself (it has no length check), so only the \\Z rule
    can refuse the newline: with $ it would match."""
    (validator,) = [
        v for v in Employee._meta.get_field(field).validators if hasattr(v, "regex")
    ]
    validator(valid)
    with pytest.raises(ValidationError):
        validator(valid + "\n")
