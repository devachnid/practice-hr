from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    """What is due across checks, policies and checklists, and the morning
    digest that reminds people of it. A small app only for its two tables:
    the reminder settings and the log of what was sent."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "compliance"
