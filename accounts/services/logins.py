"""Login accounts made for employees: the one writer of a User on the
employee's behalf. Adding an employee creates their login from the work
email (or links the unlinked login that already has it) and sends the
invitation; HR never types a password."""

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.mail import send_password_link
from accounts.models import User
from people.services import employees

WORK, PERSONAL = "work", "personal"


def existing_for(work_email):
    """The login that already has this email (case-insensitively), or None."""
    return User.objects.filter(email__iexact=work_email).select_related("employee").first()


def check_available(work_email):
    """Raise when a login with this email is already someone else's."""
    user = existing_for(work_email)
    linked = getattr(user, "employee", None) if user is not None else None
    if linked is not None:
        raise ValidationError(f"A login account with this email already belongs to {linked.name}.",
                              code="taken")
    return user


@transaction.atomic
def create_for_employee(actor, employee, request, send_to=WORK):
    """Link `employee` to the login with their work email, making it (no
    usable password, no admin status) when there is none, then send the
    invitation to the work or the personal email. Audited on the employee
    as a change of its user. Returns (user, send result): None when the
    email went, else the LinkToCopy for the admin to pass on by hand."""
    if employee.user_id is not None:
        raise ValidationError("They already have a login account.", code="linked")
    if send_to == PERSONAL and not employee.personal_email:
        raise ValidationError("Enter their personal email, or send the invitation to the work email.",
                              code="no_personal")
    user = check_available(employee.work_email)
    if user is None:
        user = User.objects.create_user(email=employee.work_email)
        user.set_unusable_password()
        user.save(update_fields=["password"])
    employees.update(actor, employee, user=user)
    to = employee.personal_email if send_to == PERSONAL else user.email
    return user, send_password_link(request, user, invite=True, to=to)
