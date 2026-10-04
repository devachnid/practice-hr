"""Starter and leaver checklists. A template (per kind, optionally per
position title) is copied into a Checklist for one employment when it
starts or ends (onboarding.services.checklists, called by
people.services.employments). Each item has an owner (HR, the line manager
or the person), a due date worked out from the start or leaving date, and
optionally a link that closes it automatically when the linked thing
happens (an upload, a signature, a recorded check)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Kind(models.TextChoices):
    STARTER = "starter", "Starter"
    LEAVER = "leaver", "Leaver"


class Owner(models.TextChoices):
    HR = "hr", "HR"
    MANAGER = "manager", "Line manager"
    PERSON = "person", "The person"


class DueRule(models.TextChoices):
    BEFORE_START = "before_start", "Days before the start date"
    AFTER_START = "after_start", "Days after the start date"
    BEFORE_END = "before_end", "Days before the leaving date"
    AFTER_END = "after_end", "Days after the leaving date"


class ChecklistTemplate(models.Model):
    kind = models.CharField(max_length=7, choices=Kind.choices)
    name = models.CharField(max_length=80)
    positions = models.ManyToManyField("people.PositionTitle", blank=True, related_name="checklist_templates",
                                       help_text="Leave empty for the default of its kind.")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name}"


class TemplateItem(models.Model):
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=10)
    title = models.CharField(max_length=120)
    instruction = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=7, choices=Owner.choices)
    due_rule = models.CharField(max_length=12, choices=DueRule.choices)
    due_days = models.PositiveSmallIntegerField(default=0)
    link = models.CharField(max_length=40, blank=True, default="",
                            help_text='"details", "upload:<category>", "sign_policies", "check:<check code>" or blank.')

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        problem = link_problem(self.link)
        if problem:
            raise ValidationError({"link": problem})


def link_problem(link):
    """Why `link` would never close an item, or "" for one the app knows."""
    from checks.models import CheckType
    from documents.models import File
    if link in ("", "details", "sign_policies"):
        return ""
    kind, _, value = link.partition(":")
    if kind == "upload" and value in File.Category.values and value != File.Category.POLICY:
        return ""
    if kind == "check" and value and CheckType.objects.filter(code=value).exists():
        return ""
    return ('Use "details", "sign_policies", "upload:" and a file category (such as upload:identity), '
            '"check:" and a check type code (such as check:dbs), or leave it blank.')


class Checklist(models.Model):
    employment = models.ForeignKey("people.Employment", on_delete=models.PROTECT, related_name="checklists")
    kind = models.CharField(max_length=7, choices=Kind.choices)
    template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)
    gaps = models.TextField(blank=True, default="", help_text="One line per set-up problem found when created.")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["employment", "kind"], name="one_checklist_per_kind")]

    def __str__(self):
        return f"{self.get_kind_display()} checklist: {self.employment.employee}"


class ChecklistItem(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        NOT_NEEDED = "not_needed", "Not needed"

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=10)
    title = models.CharField(max_length=120)
    instruction = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=7, choices=Owner.choices)
    owner_employee = models.ForeignKey("people.Employee", null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="+")
    due_on = models.DateField()
    due_rule = models.CharField(max_length=12, choices=DueRule.choices, blank=True, default="")
    link = models.CharField(max_length=40, blank=True, default="")
    state = models.CharField(max_length=10, choices=State.choices, default=State.OPEN)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    done_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["due_on", "order", "id"]

    def __str__(self):
        return self.title
