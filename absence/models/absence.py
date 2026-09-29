from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from people.models import Employment

from .types import AbsenceType


class Absence(models.Model):
    """The booking. Either a date range with half-day markers or a single
    day with times and hours (hours-unit employments only)."""
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    class Category(models.TextChoices):
        ILLNESS = "illness", "Illness"
        INJURY = "injury", "Injury"
        MENTAL_HEALTH = "mental", "Mental health"
        SURGERY = "surgery", "Surgery or procedure"
        PREGNANCY = "pregnancy", "Pregnancy-related"
        OTHER = "other", "Other"

    employment = models.ForeignKey(Employment, on_delete=models.PROTECT, related_name="absences")
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.PROTECT, related_name="absences")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.REQUESTED)
    start_date = models.DateField()
    end_date = models.DateField()
    start_half = models.CharField(max_length=2, blank=True, default="")   # "" or "PM"
    end_half = models.CharField(max_length=2, blank=True, default="")     # "" or "AM"
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cost_units = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decision_comment = models.CharField(max_length=300, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    category = models.CharField(max_length=9, choices=Category.choices, blank=True, default="")
    self_certified = models.BooleanField(default=False)
    expected_start = models.DateField(null=True, blank=True)
    actual_start = models.DateField(null=True, blank=True)
    expected_return = models.DateField(null=True, blank=True)
    auto_bank_holiday = models.BooleanField(default=False)
    chased_at = models.DateTimeField(null=True, blank=True)   # when HR were last nagged about this request

    class Meta:
        ordering = ["-start_date"]
        verbose_name_plural = "absences"

    def __str__(self):
        return f"{self.employment.employee} {self.absence_type} {self.start_date:%d %b}–{self.end_date:%d %b %Y}"

    @property
    def is_partial(self):
        return self.hours is not None

    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "Ends before it starts."})
        if self.is_partial:
            if self.start_date != self.end_date:
                raise ValidationError({"end_date": "A partial day is one day."})
            if not (self.start_time and self.end_time) or self.end_time <= self.start_time:
                raise ValidationError({"end_time": "Give a start and an end time, in order."})
            if self.hours <= 0:
                raise ValidationError({"hours": "Must be more than zero."})
        if self.start_half not in ("", "PM") or self.end_half not in ("", "AM"):
            raise ValidationError("Half-day markers are PM for the start and AM for the end.")
        if self.start_date == self.end_date and self.start_half == "PM" and self.end_half == "AM":
            raise ValidationError("A single day cannot start PM and end AM.")


class KitDay(models.Model):
    absence = models.ForeignKey(Absence, on_delete=models.CASCADE, related_name="kit_days")
    date = models.DateField()

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["absence", "date"], name="one_kit_day")]
