from django.utils import timezone

from people.services import access


def roles(request):
    """is_approver: has direct reports (the team page). can_approve: also HR
    admins, who see every queue. waiting_count is worked out only for those
    who can approve, once per request."""
    user = getattr(request, "user", None)
    if not hasattr(request, "_roles"):
        today = timezone.localdate()
        is_approver = access.is_approver(user, today) if user else False
        can_approve = is_approver or access.can_view_restricted(user)
        waiting = 0
        if can_approve:
            from absence.views.approvals import queue_for  # absence imports people, so not at the top
            waiting = queue_for(user, today).count()
        request._roles = {"is_approver": is_approver, "can_approve": can_approve, "waiting_count": waiting}
    return request._roles
