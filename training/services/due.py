"""What is due of the training, for the morning digest (compliance.due).

For each currently employed person and each required course that is due
soon, lapsed or missing: a line to every HR admin and one to the person
(always: the person does the course), keyed so the sent log applies the
schedule's cadence; the line manager once, the first time a course
lapses, naming the course (managers see training detail). A course with a
pending record says nothing to the person, who has done their part, and
asks HR to verify, keyed by the record so it repeats on the overdue
cadence until someone acts."""
from django.urls import reverse
from django.utils import timezone

from absence.services.notify import hr_admin_addresses
from compliance.due import DueItem, active_email, link, state_by_date
from people.models import Employee
from people.services import access, employments
from training.services import training

KIND = "training"
WORDS = {"online": "complete the e-learning and upload your certificate",
         "face_to_face": "ask your manager about the next session"}


def _person_url(e):
    return link(f"/training/{e.pk}/")      # training:person, registered in a later task


def due_items(today, sched):
    out = []
    hr = hr_admin_addresses()
    own_url, team_url = link(reverse("people:me")), link(reverse("people:team"))
    employed = employments.active_on(today).values("employee_id")
    for e in Employee.objects.filter(pk__in=employed).select_related("user"):
        emp = employments.current(e, today)
        if emp is None:
            continue
        person = active_email(e)
        hr_url = _person_url(e)
        for row in training.state(e, today, window_days=sched.start_days_before):
            if row.pending is not None:
                uploaded = timezone.localtime(row.pending.recorded_at).date()
                key = f"training:verify:{row.pending.pk}"
                for r in hr:
                    out.append(DueItem(e, r, KIND, f"{row.course.name}: to verify", uploaded, "to_verify", hr_url, key))
                continue
            if row.status not in training.PROBLEMS:
                continue
            # missing has no expiry: it has been owed since the employment started
            due = row.expires_on if row.status != "missing" else emp.start_date
            key = f"training:{e.pk}:{row.course.code}:{due.isoformat()}:{row.status}"
            state = state_by_date(today, due) if row.status == "due_soon" else row.status
            for r in hr:
                out.append(DueItem(e, r, KIND, row.course.name, due, state, hr_url, key))
            if person:
                out.append(DueItem(e, person, KIND, f"{row.course.name}: {WORDS[row.course.delivery]}", due, state,
                                   own_url, key))
            if row.status == "lapsed":
                manager = active_email(access.line_manager(e, today))
                if manager:
                    out.append(DueItem(e, manager, KIND, f"{row.course.name} has lapsed", due, "lapsed", team_url,
                                       key, once=True))
    return out
