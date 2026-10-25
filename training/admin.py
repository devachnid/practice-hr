"""Unfold admin over training. Courses are set up here (the titles that
need each, or everyone). Records and sessions follow in later tasks."""
from django.contrib import admin
from unfold.admin import ModelAdmin

from training.models import Course, TrainingRecord, TrainingSession


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("name", "delivery", "validity_months", "everyone", "active")
    list_editable = ("active",)
    list_filter = ("delivery", "everyone", "active")
    filter_horizontal = ("positions",)

    def get_readonly_fields(self, request, obj=None):
        # the services and the reminder keys name a course by its code:
        # settable when a course is added, never changed after
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("code",) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False                      # make it inactive instead: records point at it


# Placeholders until Task 10 replaces both.
@admin.register(TrainingRecord)
class TrainingRecordAdmin(ModelAdmin):
    list_display = ("employee", "course", "done_on", "expires_on")


@admin.register(TrainingSession)
class TrainingSessionAdmin(ModelAdmin):
    list_display = ("course", "held_on", "trainer")
