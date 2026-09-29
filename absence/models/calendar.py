from django.db import models


class BankHoliday(models.Model):
    date = models.DateField()
    name = models.CharField(max_length=60)
    nation = models.CharField(max_length=2, default="EW", help_text="EW, S or NI")

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["date", "nation"], name="one_holiday_per_day")]

    def __str__(self):
        return f"{self.name} {self.date:%d %b %Y}"


class ClosedDay(models.Model):
    """A practice closure that is not a bank holiday. Never charged."""
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=120)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.reason} {self.date:%d %b %Y}"
