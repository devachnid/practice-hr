from django.utils import timezone

from people.services import access


def roles(request):
    user = getattr(request, "user", None)
    if not hasattr(request, "_is_approver"):
        request._is_approver = access.is_approver(user, timezone.localdate()) if user else False
    return {"is_approver": request._is_approver}
