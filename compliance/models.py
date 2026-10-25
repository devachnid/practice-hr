"""The reminder settings (one row) and the log of reminders sent. The log is
what stops the digest repeating itself: an item goes to a recipient again
only when the schedule says so, counted from the last time it went."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ReminderSchedule(models.Model):
    """One row. Start X days before due, every Y days until due, every Z days overdue."""
    start_days_before = models.PositiveSmallIntegerField(
        default=60, help_text="X: the first reminder goes this many days before the due date.")
    every_days_before = models.PositiveSmallIntegerField(
        default=30, help_text="Y: then again every this many days until the due date.")
    every_days_overdue = models.PositiveSmallIntegerField(
        default=7, help_text="Z: after the due date, again every this many days while it is still outstanding.")
    registration_every_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(90)],
        verbose_name="check professional registrations every (days)",
        help_text="Each person's registration is looked up on the register again this many days after the "
                  "last time (spread by a day either way so the load is even). 1 to 90.")

    class Meta:
        verbose_name = "reminder settings"
        verbose_name_plural = "reminder settings"

    def __str__(self):
        return "Reminder settings"

    @classmethod
    def get(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row


class ReminderSent(models.Model):
    recipient = models.EmailField()
    key = models.CharField(max_length=120)
    sent_on = models.DateField()

    class Meta:
        indexes = [models.Index(fields=["recipient", "key"])]
