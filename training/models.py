"""Courses a role needs, and each person's training records. A Course says
who needs it (position titles, or everyone) and how long it lasts; a
TrainingRecord is one completion, verified when HR or a manager recorded
it, pending while a self-recorded one waits, or rejected with a note. A
TrainingSession is a face-to-face group: one verified record per attendee
points at it. Records are append-only: a renewal is a new row, and the
latest counting one by done_on is the one that counts
(training.services.training.state)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Course(models.Model):
    class Delivery(models.TextChoices):
        ONLINE = "online", "Online"
        FACE_TO_FACE = "face_to_face", "Face to face"

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)],
                                                       help_text="Blank: a one-off course that is never renewed.")
    everyone = models.BooleanField(default=False, verbose_name="required of everyone",
                                   help_text="Every currently employed person needs it, whatever their title.")
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="courses",
                                       help_text="The titles that need this course (ignored when it is required "
                                                 "of everyone).")
    delivery = models.CharField(max_length=12, choices=Delivery.choices, default=Delivery.ONLINE,
                                help_text="Online: a self-recorded completion needs its certificate. Face to "
                                          "face: usually recorded as a session.")
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class TrainingSession(models.Model):
    """A face-to-face group on one day. Recording one makes a verified
    TrainingRecord per attendee (training.services.sessions)."""
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="sessions")
    held_on = models.DateField()
    trainer = models.CharField(max_length=120, blank=True, default="",
                               help_text="An outside provider or a colleague's name.")
    note = models.TextField(blank=True, default="")
    attendance_sheet = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT,
                                         related_name="attendance_sheet_of")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-held_on", "-id"]

    def __str__(self):
        return f"{self.course} on {self.held_on:%d %b %Y}"


class TrainingRecord(models.Model):
    employee = models.ForeignKey("people.Employee", on_delete=models.PROTECT, related_name="training_records")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="records")
    done_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, default="", help_text="Seen by HR and the line manager, never the person.")
    certificate = models.ForeignKey("documents.File", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="certificate_of")
    session = models.ForeignKey(TrainingSession, null=True, blank=True, on_delete=models.PROTECT,
                                related_name="records")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-done_on", "-id"]
        indexes = [models.Index(fields=["employee", "course"])]

    def __str__(self):
        return f"{self.course} for {self.employee}"

    @property
    def rejected(self):
        return self.rejected_at is not None

    @property
    def counts(self):
        return self.verified_at is not None and self.rejected_at is None

    @property
    def pending(self):
        return self.verified_at is None and self.rejected_at is None
