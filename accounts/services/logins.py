"""Login accounts made for employees: the one writer of a User on the
employee's behalf. Adding an employee creates their login from the work
email (or links the unlinked login that already has it); HR never types a
password. The invitation is the admin's to send once the add has
committed (people.admin), never from inside the transaction."""

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from people.services import employees

WORK, PERSONAL = "work", "personal"


def existing_for(work_email):
    """The login that already has this email (as the model stores it,
    case-insensitively), or None."""
    email = User.objects.normalize_email(work_email)
    return User.objects.filter(email__iexact=email).select_related("employee").first()


def check_available(work_email, actor, send_to=WORK):
    """The login the add may link for this email: None when there is none
    (one will be made), else the existing one — refused when it is already
    someone's, inactive, a superuser's (unless the actor is one: an HR admin
    must never gain a superuser's reset link), or when the invitation is to
    go anywhere but its own address (a link for an existing login is only
    ever sent to that login)."""
    user = existing_for(work_email)
    if user is None:
        return None
    linked = getattr(user, "employee", None)
    if linked is not None:
        raise ValidationError(f"A login account with this email already belongs to {linked.name}.", code="taken")
    if user.is_superuser and not getattr(actor, "is_superuser", False):
        raise ValidationError("A login account with this email already exists and cannot be linked here.",
                              code="superuser")
    if not user.is_active:
        raise ValidationError("That login account is inactive: reactivate it under Login accounts, or correct "
                              "the work email.", code="inactive")
    if send_to == PERSONAL:
        raise ValidationError("A login account with this email already exists; send its invitation to the "
                              "work email.", code="existing_personal")
    return user


@transaction.atomic
def create_for_employee(actor, employee, send_to=WORK):
    """Link `employee` to the login with their work email, making it (no
    usable password, no admin status) when there is none. Audited on the
    employee as a change of its user. Returns (user, invite): invite is
    True when the login has no password yet and the invitation should be
    sent (to the personal email when `send_to` says so), False for an
    existing login that already has one."""
    if employee.user_id is not None:
        raise ValidationError("They already have a login account.", code="linked")
    if send_to == PERSONAL and not employee.personal_email:
        raise ValidationError("Enter their personal email, or send the invitation to the work email.",
                              code="no_personal")
    user = check_available(employee.work_email, actor, send_to)
    if user is None:
        user = User.objects.create_user(email=employee.work_email)      # no password: unusable until invited
    employees.update(actor, employee, user=user)
    return user, not user.has_usable_password()
