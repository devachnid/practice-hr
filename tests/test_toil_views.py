"""The TOIL claim pages: claim your own, record one for a report, decide,
cancel; and where claims show up (the queue and its count, My absences,
team balances, the admin dashboard). Dates are offsets from today."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, RequestFactory
from django.utils import timezone

from absence.models import AbsenceType, LedgerEntry, Pot, ToilClaim
from absence.services import toil
from people.context_processors import roles
from people.services import positions
from tests.factories import current_leave_year, hours_employee, make_employee, make_employment, make_team

D = Decimal
S = ToilClaim.Status
User = get_user_model()


def _today():
    return timezone.localdate()


def _worked(days_ago=3):
    return _today() - timedelta(days=days_ago)


def _people(employee_user):
    """Sam (employee_user) reports to Boss. Returns (sam's employment, a client logged in as Boss, Boss's user)."""
    start = current_leave_year()[0] - timedelta(days=400)
    boss_user = User.objects.create_user(email="boss@example.org", password="pw")
    boss = make_employee(first="Boss", last="Jones", user=boss_user)
    make_employment(employee=boss, start=start)
    emp = hours_employee(start=start, employee=make_employee(user=employee_user))
    positions.add(None, emp, "Receptionist", make_team(), boss, start)
    c = Client()
    c.force_login(boss_user)
    return emp, c, boss_user


def _stranger():
    u = User.objects.create_user(email="stranger@example.org", password="pw")
    hours_employee(employee=make_employee(first="Stranger", user=u))
    c = Client()
    c.force_login(u)
    return c


def _form(day=None, units="2.5", reason="Late clinic"):
    return {"day": str(day or _worked()), "units": units, "reason": reason}


def _claim(employee_user, emp, **kw):
    d = _form(**kw)
    return toil.claim(employee_user, emp, timezone.datetime.fromisoformat(d["day"]).date(), D(d["units"]),
                      d["reason"])


# --- claiming your own -------------------------------------------------------------------------

def test_the_claim_page_asks_for_the_day_the_time_and_why(employee_client, employee_user):
    _people(employee_user)
    r = employee_client.get("/absence/toil/claim/")
    body = r.content.decode()
    assert r.status_code == 200 and "<h1>Claim TOIL</h1>" in body
    for name in ("day", "units", "reason"):
        assert f'name="{name}"' in body
    assert 'step="0.25"' in body and f'max="{_today():%Y-%m-%d}"' in body
    assert not ToilClaim.objects.exists() and not Pot.objects.exists()


def test_claiming_sends_it_to_the_approver(configured, employee_client, employee_user):
    emp, _, _ = _people(employee_user)
    r = employee_client.post("/absence/toil/claim/", _form(), follow=True)
    assert r.redirect_chain[-1][0] == "/absence/mine/"
    c = ToilClaim.objects.get()
    assert (c.employment, c.status, c.units, c.requested_by) == (emp, S.REQUESTED, D("2.5"), employee_user)
    assert "Sent for approval." in r.content.decode()
    assert mail.outbox[-1].subject == "TOIL claim from Sam Patel" and mail.outbox[-1].to == ["boss.jones.1@example.org"]


def test_a_claim_email_that_does_not_go_gives_the_link(employee_client, employee_user):
    _people(employee_user)                                               # email not configured
    body = employee_client.post("/absence/toil/claim/", _form(), follow=True).content.decode()
    c = ToilClaim.objects.get()
    assert "Saved and waiting for approval" in body and f"/absence/toil/{c.pk}/decide/" in body


def test_a_refused_claim_shows_why_and_saves_nothing(employee_client, employee_user):
    _people(employee_user)
    r = employee_client.post("/absence/toil/claim/", _form(day=_today() + timedelta(days=1)))
    assert r.status_code == 200 and "already worked" in r.content.decode()
    r = employee_client.post("/absence/toil/claim/", _form(units="1.1"))
    assert "steps of 0.25 hours" in r.content.decode()
    assert not ToilClaim.objects.exists()


def test_someone_with_no_employee_record_is_told_so(employee_client):
    r = employee_client.get("/absence/toil/claim/")
    assert r.status_code == 200 and "no employee record" in r.content.decode()


# --- recording one for a report ----------------------------------------------------------------

def test_the_approver_records_a_claim_for_a_report_approved_at_once(configured, employee_user):
    emp, boss, boss_user = _people(employee_user)
    url = f"/absence/toil/claim/{emp.employee.pk}/"
    r = boss.get(url)
    assert r.status_code == 200 and "<h1>Record TOIL for Sam Patel</h1>" in r.content.decode()
    r = boss.post(url, _form(units="3", reason="Covered the late surgery"), follow=True)
    assert r.redirect_chain[-1][0] == f"/absence/balances/{emp.employee.pk}/"
    c = ToilClaim.objects.get()
    assert (c.status, c.decided_by, c.requested_by) == (S.APPROVED, boss_user, boss_user)
    assert c.earned.units == D("3") and c.earned.date == _worked()
    assert mail.outbox[-1].subject == "Your TOIL claim was approved"


def test_recording_for_someone_is_for_their_approver_or_hr_only(employee_user, admin_client):
    emp, _, _ = _people(employee_user)
    url = f"/absence/toil/claim/{emp.employee.pk}/"
    assert _stranger().get(url).status_code == 403
    assert _stranger_post(url) == 403
    assert admin_client.get(url).status_code == 200
    assert not ToilClaim.objects.exists()


def _stranger_post(url):
    c = Client()
    c.force_login(User.objects.get(email="stranger@example.org"))
    return c.post(url, _form()).status_code


def test_recording_for_yourself_goes_to_your_own_claim(employee_client, employee_user):
    emp, _, _ = _people(employee_user)
    r = employee_client.get(f"/absence/toil/claim/{emp.employee.pk}/")
    assert r.status_code == 302 and r["Location"] == "/absence/toil/claim/"


# --- deciding ----------------------------------------------------------------------------------

def test_the_decide_page_shows_the_claim_and_their_toil(employee_user):
    emp, boss, boss_user = _people(employee_user)
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=30)
    toil.claim(boss_user, emp, _worked(10), D("4"), "Flu clinic")                  # expires in 20 days
    c = _claim(employee_user, emp)
    before = LedgerEntry.objects.count()
    r = boss.get(f"/absence/toil/{c.pk}/decide/")
    body = r.content.decode()
    assert r.status_code == 200 and "Sam Patel: TOIL claim" in body
    assert "Late clinic" in body and "2.50 hours" in body and f"{_worked():%-d %b %Y}" in body
    assert "Remaining now" in body and "4 hours" in body
    expires = _worked(10) + timedelta(days=30)
    assert f"{expires:%-d %b %Y}" in body                                         # the lot expiring soon
    assert 'value="approve"' in body and LedgerEntry.objects.count() == before


def test_the_decide_page_is_refused_to_strangers_and_the_claimant(employee_user, employee_client, admin_client):
    emp, _, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    url = f"/absence/toil/{c.pk}/decide/"
    assert _stranger().get(url).status_code == 403
    assert employee_client.get(url).status_code == 403
    assert employee_client.post(url, {"action": "approve"}).status_code == 403
    assert admin_client.get(url).status_code == 200
    assert ToilClaim.objects.get().status == S.REQUESTED


def test_approving_on_the_decide_page(configured, employee_user):
    emp, boss, boss_user = _people(employee_user)
    c = _claim(employee_user, emp)
    r = boss.post(f"/absence/toil/{c.pk}/decide/", {"action": "approve", "comment": "Thanks"}, follow=True)
    assert r.redirect_chain[-1][0] == "/absence/queue/"
    c.refresh_from_db()
    assert c.status == S.APPROVED and c.decision_comment == "Thanks" and c.earned.units == D("2.5")
    assert "TOIL claim for Sam Patel: approved." in r.content.decode()
    assert mail.outbox[-1].subject == "Your TOIL claim was approved"


def test_declining_on_the_decide_page_writes_nothing(employee_user):
    emp, boss, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    boss.post(f"/absence/toil/{c.pk}/decide/", {"action": "decline", "comment": "Not agreed"})
    assert ToilClaim.objects.get().status == S.DECLINED and not LedgerEntry.objects.exists()


def test_a_decided_claim_is_read_only(employee_user):
    emp, boss, boss_user = _people(employee_user)
    c = toil.approve(boss_user, _claim(employee_user, emp))
    url = f"/absence/toil/{c.pk}/decide/"
    body = boss.get(url).content.decode()
    assert "Already approved by Boss Jones" in body and 'value="approve"' not in body
    boss.post(url, {"action": "decline"})
    assert ToilClaim.objects.get().status == S.APPROVED
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.TOIL_EARNED).count() == 1


# --- cancelling --------------------------------------------------------------------------------

def test_the_claimant_cancels_a_waiting_claim(employee_client, employee_user):
    emp, boss, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    url = f"/absence/toil/{c.pk}/cancel/"
    assert employee_client.get(url).status_code == 405
    assert boss.post(url).status_code == 403
    r = employee_client.post(url, follow=True)
    assert r.redirect_chain[-1][0] == "/absence/mine/" and "Claim cancelled." in r.content.decode()
    assert ToilClaim.objects.get().status == S.CANCELLED


def test_an_approved_claim_cannot_be_cancelled(employee_client, employee_user):
    emp, _, boss_user = _people(employee_user)
    c = toil.approve(boss_user, _claim(employee_user, emp))
    assert employee_client.post(f"/absence/toil/{c.pk}/cancel/").status_code == 403
    assert ToilClaim.objects.get().status == S.APPROVED


# --- where claims show up ----------------------------------------------------------------------

def test_the_queue_lists_the_claims_waiting_on_the_approver(employee_user, admin_client):
    emp, boss, _ = _people(employee_user)
    body = boss.get("/absence/queue/").content.decode()
    assert "<h2>TOIL claims waiting</h2>" in body and "No TOIL claims waiting." in body
    c = _claim(employee_user, emp)
    body = boss.get("/absence/queue/").content.decode()
    section = body[body.index("<h2>TOIL claims waiting</h2>"):]
    for heading in ("Who", "Day", "Amount", "Reason", "Asked"):
        assert f"<th>{heading}</th>" in section
    assert "Sam Patel" in section and "2.50 hours" in section and "Late clinic" in section
    assert f'<a href="/absence/toil/{c.pk}/decide/" class="btn">Decide</a>' in section
    assert "Approvals (1)" in body
    assert f"/absence/toil/{c.pk}/decide/" not in _stranger_queue()
    assert f"/absence/toil/{c.pk}/decide/" in admin_client.get("/absence/queue/").content.decode()


def _stranger_queue():
    """A second approver, of someone else: never sees Sam's claim."""
    u = User.objects.create_user(email="other.boss@example.org", password="pw")
    other_boss = make_employee(first="Other", last="Boss", user=u)
    make_employment(employee=other_boss, start=_today() - timedelta(days=100))
    report = hours_employee(employee=make_employee(first="Peer"))
    positions.add(None, report, "Nurse", make_team("Nursing"), other_boss, report.start_date)
    c = Client()
    c.force_login(u)
    return c.get("/absence/queue/").content.decode()


def test_the_waiting_count_includes_claims(employee_user):
    emp, _, boss_user = _people(employee_user)
    _claim(employee_user, emp)
    request = RequestFactory().get("/")
    request.user = boss_user
    assert roles(request)["waiting_count"] == 1


def test_my_absences_has_a_toil_card(employee_client, employee_user):
    emp, _, boss_user = _people(employee_user)
    body = employee_client.get("/absence/mine/").content.decode()
    card = body[body.index("<h2>TOIL</h2>"):]
    assert '<a href="/absence/toil/claim/" class="btn">Claim TOIL</a>' in card
    assert "Remaining now" in card and "0 hours" in card and "Nothing waiting." in card
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=30)
    toil.claim(boss_user, emp, _worked(10), D("4"), "Flu clinic")
    waiting = _claim(employee_user, emp)
    body = employee_client.get("/absence/mine/").content.decode()
    card = body[body.index("<h2>TOIL</h2>"):]
    assert "4 hours" in card and "Late clinic" in card
    assert f'action="/absence/toil/{waiting.pk}/cancel/"' in card
    assert f"{_worked(10) + timedelta(days=30):%-d %b %Y}" in card


def test_team_balances_offers_record_toil_to_the_approver(employee_user):
    emp, boss, _ = _people(employee_user)
    body = boss.get("/absence/balances/team/").content.decode()
    assert f'<a href="/absence/toil/claim/{emp.employee.pk}/" class="btn btn-quiet">Record TOIL for Sam Patel</a>' in body


def test_the_admin_dashboard_lists_a_claim_waiting_too_long(employee_user, admin_client):
    emp, _, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    ToilClaim.objects.filter(pk=c.pk).update(requested_at=timezone.now() - timedelta(days=14))
    body = admin_client.get("/admin/").content.decode()
    assert f'href="/absence/toil/{c.pk}/decide/"' in body and "TOIL claim" in body


def test_the_claim_page_says_how_far_back_a_claim_may_go(employee_client, employee_user):
    _people(employee_user)
    body = employee_client.get("/absence/toil/claim/").content.decode()
    assert "Today or earlier, up to 365 days ago" in body
    r = employee_client.post("/absence/toil/claim/", _form(day=_today() - timedelta(days=366)))
    assert "more than 365 days ago, so it would already have expired" in r.content.decode()
    assert not ToilClaim.objects.exists()


def test_the_claim_page_reads_only_a_blank_expiry_as_no_limit(employee_client, employee_user):
    _people(employee_user)
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=None)
    body = employee_client.get("/absence/toil/claim/").content.decode()
    assert "days ago" not in body and "days after the day you worked it" not in body
    AbsenceType.objects.filter(code="TOIL").update(earned_expires_after_days=0)       # as the day itself
    body = employee_client.get("/absence/toil/claim/").content.decode()
    assert "up to 0 days ago" in body and "0 days after the day you worked it" in body


def test_the_dashboard_counts_requests_and_claims_apart(employee_user, admin_client):
    emp, _, _ = _people(employee_user)
    c = _claim(employee_user, emp)
    ToilClaim.objects.filter(pk=c.pk).update(requested_at=timezone.now() - timedelta(days=14))
    body = admin_client.get("/admin/").content.decode()
    assert "1 TOIL claim waiting more than" in body and "request" not in body.split("TOIL claim waiting")[0][-40:]
