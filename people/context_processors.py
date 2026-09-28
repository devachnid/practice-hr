from datetime import date

from people.services import access


def roles(request):
    user = getattr(request, "user", None)
    if not hasattr(request, "_is_approver"):
        request._is_approver = access.is_approver(user, date.today()) if user else False
    return {"is_approver": request._is_approver}
