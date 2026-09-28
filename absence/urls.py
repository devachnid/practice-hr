from django.urls import path

from absence.views import approvals, balances, calendar, requests

app_name = "absence"
urlpatterns = [
    path("request/", requests.request_leave, name="request"),
    path("mine/", requests.mine, name="mine"),
    path("calendar/", calendar.calendar_view, name="calendar"),
    path("balances/", balances.balances_view, name="balances"),
    path("balances/team/", balances.team, name="balances_team"),
    path("balances/<int:pk>/", balances.balances_for, name="balances_for"),
    path("ledger/<int:pk>/", balances.ledger_view, name="ledger"),
    path("queue/", approvals.queue, name="queue"),
    # exactly notify.DECIDE_PATH: the link in the approver's email
    path("decide/<int:pk>/", approvals.decide, name="decide"),
    path("<int:pk>/cancel/", requests.cancel, name="cancel"),
    path("<int:pk>/kit-day/", requests.kit_day, name="kit_day"),
]
