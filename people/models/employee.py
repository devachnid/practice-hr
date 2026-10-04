from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


class Employee(models.Model):
    """The person, created once and never deleted. Employment spells,
    contracts and everything dated hang off Employment, not here."""
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    preferred_name = models.CharField(max_length=60, blank=True, default="")
    work_email = models.EmailField(
        help_text="The practice email address, unique whatever its case. It is the email "
                  "the rota's read API sends for this person; at sign-in the rota receives the "
                  "login account's email instead, so keep the two the same. Sign-in does not "
                  "read it: the User field below is what links this record to a login account.")
    personal_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    address_line1 = models.CharField(max_length=120, blank=True, default="")
    address_line2 = models.CharField(max_length=120, blank=True, default="")
    town = models.CharField(max_length=60, blank=True, default="")
    postcode = models.CharField(max_length=10, blank=True, default="")
    ni_number = models.CharField("NI number", max_length=9, blank=True, default="")
    bank_account_name = models.CharField(max_length=60, blank=True, default="")
    bank_sort_code = models.CharField(
        max_length=8, blank=True, default="",
        validators=[RegexValidator(r"^\d{2}-\d{2}-\d{2}$", "Enter the sort code as NN-NN-NN.")])
    bank_account_number = models.CharField(
        max_length=8, blank=True, default="",
        validators=[RegexValidator(r"^\d{8}$", "An account number is eight digits.")])
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employee")

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(Lower("work_email"), name="employee_work_email_ci_unique"),
        ]

    @property
    def name(self):
        return f"{self.preferred_name or self.first_name} {self.last_name}"

    def __str__(self):
        return self.name


class EmergencyContact(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=60, blank=True, default="")
    phone = models.CharField(max_length=30)
    priority = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.relationship})"
