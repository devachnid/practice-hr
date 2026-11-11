from django.utils import timezone

from people.services import access


def roles(request):
    """is_approver: has direct reports (the team page). can_approve: also HR
    admins, who see every queue. waiting_count (leave requests and TOIL
    claims) is worked out only for those who can approve, once per request.
    leave_url: Shift Central's address when leave is held there
    (absence/elsewhere.py), which takes the leave links out of the navigation."""
    user = getattr(request, "user", None)
    if not hasattr(request, "_roles"):
        today = timezone.localdate()
        is_approver = access.is_approver(user, today) if user else False
        can_approve = is_approver or access.can_view_restricted(user)
        waiting = 0
        from absence import elsewhere      # absence imports people, so not at the top
        leave_url = elsewhere.url()
        if can_approve and not leave_url:
            # absence imports people, so not at the top
            from absence.views.approvals import claims_for, queue_for
            waiting = queue_for(user, today).count() + claims_for(user, today).count()
        request._roles = {"is_approver": is_approver, "can_approve": can_approve, "waiting_count": waiting,
                          "leave_url": leave_url}
    return request._roles
