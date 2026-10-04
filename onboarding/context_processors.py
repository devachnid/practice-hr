from onboarding.middleware import pre_start as _pre_start
from onboarding.models import ChecklistItem, Owner
from people.services import access


def pre_start(request):
    """pre_start: base.html hides the navigation from a starter before their
    first day (onboarding.middleware). has_todo: open line-manager checklist
    items of theirs, so My team is in the navigation for a manager whose
    starter has not started yet (and so is no direct report today)."""
    if _pre_start(request):
        return {"pre_start": True, "has_todo": False}
    me = access.employee_for(getattr(request, "user", None))
    has_todo = me is not None and ChecklistItem.objects.filter(
        owner_employee=me, owner=Owner.MANAGER, state=ChecklistItem.State.OPEN).exists()
    return {"pre_start": False, "has_todo": has_todo}
