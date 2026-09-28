from datetime import date

from people.models import Employee

MON = date(2026, 4, 6)  # a Monday, in the 2026/27 leave year


def make_employee(first="Sam", last="Patel", email=None, **kw):
    """Default emails carry a counter so two default employees never collide."""
    email = email or f"{first}.{last}.{Employee.objects.count() + 1}@example.org".lower()
    return Employee.objects.create(first_name=first, last_name=last, work_email=email, **kw)
