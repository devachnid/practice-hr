from django.contrib.auth import get_user_model

from people.models import Employee
from people.services import employments


def run(today):
    """Disable the login of anyone whose employment has ended and who has
    no spell on or after today. Idempotent."""
    User = get_user_model()
    disabled = 0
    for employee in Employee.objects.filter(user__isnull=False, user__is_active=True).select_related("user"):
        if employments.current(employee, today) is not None:
            continue
        if employee.employments.filter(start_date__gt=today).exists():
            continue
        if not employee.employments.exists():
            continue
        User.objects.filter(pk=employee.user_id).update(is_active=False)
        disabled += 1
    return {"logins_disabled": disabled}
