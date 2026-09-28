from datetime import date

from people.services import access


def roles(request):
    user = getattr(request, "user", None)
    return {"is_approver": access.is_approver(user, date.today()) if user else False}
