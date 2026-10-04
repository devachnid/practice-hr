"""The only writer of Checklist and ChecklistItem rows.

A starter checklist is built when an employment starts (employments.start,
within RECENT_DAYS of today), a leaver checklist when its end date is set
(employments.end). The template is the active one of that kind whose
positions include the title of the primary position, else the default of
the kind (no positions). Items are owned by HR, the line manager of the
primary position, or the person; a missing owner, position or template is
recorded in Checklist.gaps, never raised: a checklist must never stop an
employment being saved.

The admin saves an employment before its positions, so positions.add calls
position_added(): a starter checklist nobody has worked on yet is rebuilt
from the title's template, and open manager items get the line manager.

Linked items close themselves (linked_done) when the linked thing happens:
"details" (Task 7's form), "upload:<file category>" (files.ADDED_HOOKS),
"sign_policies" (policies.SIGNED_HOOKS, once nothing is owed) and
"check:<check type code>" (checks.RECORDED_HOOKS). The hooks run inside the
caller's transaction, so linked_done never raises for an ordinary case: no
matching item is a no-op."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from onboarding.models import Checklist, ChecklistItem, ChecklistTemplate, DueRule, Kind, Owner
from people.services import access, audit, positions

RECENT_DAYS = 30
START_RULES = (DueRule.BEFORE_START, DueRule.AFTER_START)
END_RULES = (DueRule.BEFORE_END, DueRule.AFTER_END)
AUTOMATIC = "done automatically"


def _template(kind, title):
    qs = ChecklistTemplate.objects.filter(kind=kind, active=True)
    if title is not None:
        hit = qs.filter(positions=title).first()
        if hit:
            return hit
    return qs.filter(positions=None).first()


def _due(rule, days, start, end):
    if rule == DueRule.BEFORE_START:
        return start - timedelta(days=days)
    if rule == DueRule.AFTER_START:
        return start + timedelta(days=days)
    if rule == DueRule.BEFORE_END:
        return end - timedelta(days=days)
    return end + timedelta(days=days)


def _anchor(employment, kind):
    return employment.start_date if kind == Kind.STARTER else employment.end_date


def _resolve(employment, kind):
    """(position, template, manager) on the checklist's anchor date."""
    pos = positions.primary_on(employment, _anchor(employment, kind))
    template = _template(kind, pos.title if pos else None)
    return pos, template, (pos.line_manager if pos else None)


def _gaps(kind, pos, template, manager):
    gaps = []
    if pos is None:
        gaps.append("no position on the anchor date, so no title to match a template")
    if template is None:
        gaps.append(f"no {kind} checklist template (add one in Admin › Compliance › Checklist templates)")
    if manager is None:
        gaps.append("no line manager on the primary position: manager items have no owner")
    return gaps


def _owner_employee(owner, employment, manager):
    return {Owner.MANAGER: manager, Owner.PERSON: employment.employee}.get(owner)


def _copy_items(checklist, template, manager):
    employment = checklist.employment
    for it in (template.items.all() if template else []):
        ChecklistItem.objects.create(
            checklist=checklist, order=it.order, title=it.title, instruction=it.instruction, owner=it.owner,
            owner_employee=_owner_employee(it.owner, employment, manager), due_rule=it.due_rule, link=it.link,
            due_on=_due(it.due_rule, it.due_days, employment.start_date, employment.end_date or employment.start_date))


def _build(actor, employment, kind):
    pos, template, manager = _resolve(employment, kind)
    cl = Checklist.objects.create(employment=employment, kind=kind, template=template, created_by=actor,
                                  gaps="\n".join(_gaps(kind, pos, template, manager)))
    _copy_items(cl, template, manager)
    audit.record(actor, cl, {"created": ("", f"{kind} checklist, {cl.items.count()} items")})
    return cl


def _shift(actor, checklist, rules, delta):
    """Move the open items due by `rules` when the date they hang on moves."""
    if checklist is None or not delta:
        return
    moved = 0
    for item in checklist.items.filter(state=ChecklistItem.State.OPEN, due_rule__in=rules):
        item.due_on += delta
        item.save(update_fields=["due_on"])
        moved += 1
    if moved:
        audit.record(actor, checklist, {"due_dates": ("", f"{moved} open items moved by {delta.days} days")})


@transaction.atomic
def start(actor, employment):
    """Called by employments.start. None for a spell that began more than
    RECENT_DAYS ago (a past spell entered after the fact)."""
    today = timezone.localdate()
    if employment.start_date < today - timedelta(days=RECENT_DAYS):
        return None
    existing = Checklist.objects.filter(employment=employment, kind=Kind.STARTER).first()
    if existing:
        return existing
    return _build(actor, employment, Kind.STARTER)


@transaction.atomic
def leave(actor, employment, previous_end=None):
    """Called by employments.end when an end date is set. A leaver
    checklist already there is kept; when `previous_end` says the date
    moved, its open items due by the leaving date move with it."""
    if employment.end_date is None:
        return None
    existing = Checklist.objects.filter(employment=employment, kind=Kind.LEAVER).first()
    if existing:
        if previous_end is not None:
            _shift(actor, existing, END_RULES, employment.end_date - previous_end)
        return existing
    return _build(actor, employment, Kind.LEAVER)


def _untouched(checklist):
    """Nothing closed, added or removed by hand since it was built."""
    items = list(checklist.items.all())
    expected = checklist.template.items.count() if checklist.template else 0
    return (len(items) == expected and all(i.state == ChecklistItem.State.OPEN and i.due_rule for i in items))


@transaction.atomic
def position_added(actor, position):
    """Called by positions.add. The starter checklist is built when the
    employment is saved, which in the admin is before its positions: a
    primary position covering the start date brings the title's template
    (while nobody has worked on the checklist) and the line manager."""
    if not position.primary:
        return None
    employment = position.employment
    cl = Checklist.objects.filter(employment=employment, kind=Kind.STARTER, completed_at__isnull=True).first()
    if cl is None:
        return None
    pos, template, manager = _resolve(employment, Kind.STARTER)
    if pos is None or pos.pk != position.pk:
        return cl
    gaps = _gaps(Kind.STARTER, pos, template, manager)
    changes = {}
    if template != cl.template:
        if _untouched(cl):
            changes["template"] = (cl.template or "", template or "")
            cl.items.all().delete()
            cl.template = template
            _copy_items(cl, template, manager)
        else:
            gaps.append(f"the template for {pos.title} ({template}) was not applied: work on this checklist "
                        "had begun")
    moved = (cl.items.filter(owner=Owner.MANAGER, state=ChecklistItem.State.OPEN)
             .exclude(owner_employee=manager).update(owner_employee=manager))
    if moved:
        changes["manager_items"] = ("", f"{moved} open items to {manager or 'nobody'}")
    cl.gaps = "\n".join(gaps)
    cl.save(update_fields=["template", "gaps"])
    audit.record(actor, cl, changes)
    return cl


@transaction.atomic
def start_moved(actor, employment, previous_start):
    """Called by employments.amend: the starter checklist's open items due
    by the start date move with it."""
    cl = Checklist.objects.filter(employment=employment, kind=Kind.STARTER).first()
    _shift(actor, cl, START_RULES, employment.start_date - previous_start)


def gaps(checklist):
    return [g for g in checklist.gaps.splitlines() if g]


def may_complete(user, item):
    if access.can_view_restricted(user):
        return True
    me = access.employee_for(user)
    return me is not None and item.owner_employee_id == me.pk


def _finish_if_done(checklist):
    if checklist.completed_at is None and not checklist.items.filter(state=ChecklistItem.State.OPEN).exists():
        checklist.completed_at = timezone.now()
        checklist.save(update_fields=["completed_at"])


def _close(actor, item, state, note):
    """Re-read under a lock so two closes cannot both succeed; the caller's
    instance is updated to match."""
    locked = ChecklistItem.objects.select_for_update().get(pk=item.pk)
    if locked.state != ChecklistItem.State.OPEN:
        raise ValidationError("Already closed.")
    note = (note or "")[:200]
    for it in (locked, item):
        it.state, it.done_by, it.done_at, it.note = state, actor, timezone.now(), note
    locked.save(update_fields=["state", "done_by", "done_at", "note"])
    audit.record(actor, locked, {"state": (ChecklistItem.State.OPEN, state)}, note=note)
    _finish_if_done(locked.checklist)
    return item


@transaction.atomic
def complete(actor, item, note=""):
    if not may_complete(actor, item):
        raise PermissionDenied
    return _close(actor, item, ChecklistItem.State.DONE, note)


@transaction.atomic
def not_needed(actor, item, note):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    if not (note or "").strip():
        raise ValidationError("Say why it is not needed.")
    return _close(actor, item, ChecklistItem.State.NOT_NEEDED, note)


@transaction.atomic
def add_item(actor, checklist, title, instruction, owner, due_on, link=""):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    if owner not in Owner.values:
        raise ValidationError("Choose who does it.")
    emp = checklist.employment
    # the manager the template's items got: the one on the checklist's anchor
    # date (a leaver's item due after the leaving date still has one)
    manager = _resolve(emp, checklist.kind)[2] if owner == Owner.MANAGER else None
    item = ChecklistItem(checklist=checklist, order=(checklist.items.count() + 1) * 10, title=title,
                         instruction=instruction, owner=owner, owner_employee=_owner_employee(owner, emp, manager),
                         due_on=due_on, link=link)
    item.full_clean()
    item.save()
    if checklist.completed_at is not None:
        checklist.completed_at = None
        checklist.save(update_fields=["completed_at"])
    audit.record(actor, item, {"added": ("", title)})
    return item


@transaction.atomic
def remove_item(actor, item):
    if not access.can_view_restricted(actor):
        raise PermissionDenied
    checklist = item.checklist
    audit.record(actor, checklist, {"removed": (item.title, "")})
    item.delete()
    _finish_if_done(checklist)


def _value(choice):
    return getattr(choice, "value", choice)


@transaction.atomic
def linked_done(employee, link_prefix, *, category=None, check_code=None):
    """Close every open item of `employee` whose link is `link_prefix`, or
    `link_prefix:<category or check_code>` when one is given ("upload",
    category="identity" is "upload:identity"). No matching item, or no
    employee, is a no-op: this runs inside the caller's transaction. Returns
    the number closed."""
    if employee is None or employee.pk is None:
        return 0
    suffix = category if category is not None else check_code
    link = f"{link_prefix}:{_value(suffix)}" if suffix else link_prefix
    items = list(ChecklistItem.objects.select_for_update()
                 .filter(checklist__employment__employee=employee, link=link, state=ChecklistItem.State.OPEN)
                 .select_related("checklist"))
    now = timezone.now()
    for item in items:
        item.state, item.done_at, item.note = ChecklistItem.State.DONE, now, AUTOMATIC
        item.save(update_fields=["state", "done_at", "note"])
        audit.record(None, item, {"state": (ChecklistItem.State.OPEN, ChecklistItem.State.DONE)}, note=AUTOMATIC)
    for checklist in {item.checklist_id: item.checklist for item in items}.values():
        _finish_if_done(checklist)
    return len(items)


# ---- the hooks (registered in onboarding.apps.OnboardingConfig.ready) ---------

def on_check_recorded(check):
    linked_done(check.employee, "check", check_code=check.check_type.code)


def on_policy_signed(employee):
    from documents.services import policies
    if not policies.owed(employee, timezone.localdate()):
        linked_done(employee, "sign_policies")


def on_file_added(file):
    if file.employee_id:
        linked_done(file.employee, "upload", category=file.category)


# ---- reads -------------------------------------------------------------------

def open_items(employee, today):
    """The person's own open items, every checklist of theirs."""
    return list(ChecklistItem.objects.filter(checklist__employment__employee=employee, owner=Owner.PERSON,
                                             state=ChecklistItem.State.OPEN)
                .select_related("checklist").order_by("due_on", "order"))


def items_owned_by(manager_employee, today):
    """The open manager items a line manager owns, across their reports."""
    return list(ChecklistItem.objects.filter(owner_employee=manager_employee, owner=Owner.MANAGER,
                                             state=ChecklistItem.State.OPEN)
                .select_related("checklist__employment__employee").order_by("due_on", "order"))


def summary(checklist):
    items = list(checklist.items.all())
    today = timezone.localdate()
    open_ = [i for i in items if i.state == ChecklistItem.State.OPEN]
    overdue = sorted((i for i in open_ if i.due_on < today), key=lambda i: (i.due_on, i.order, i.pk))
    return {"total": len(items), "done": len(items) - len(open_), "open": len(open_), "overdue": len(overdue),
            "oldest_overdue": overdue[0] if overdue else None}
