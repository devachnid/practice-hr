from django.urls import path

from absence.views import approvals, calendar, requests

app_name = "absence"
urlpatterns = [
    path("request/", requests.request_leave, name="request"),
    path("mine/", requests.mine, name="mine"),
    path("calendar/", calendar.calendar_view, name="calendar"),
    path("queue/", approvals.queue, name="queue"),
    # exactly notify.DECIDE_PATH: the link in the approver's email
    path("decide/<int:pk>/", approvals.decide, name="decide"),
    path("<int:pk>/cancel/", requests.cancel, name="cancel"),
    path("<int:pk>/kit-day/", requests.kit_day, name="kit_day"),
]
