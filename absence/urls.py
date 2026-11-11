from django.urls import path

from absence.elsewhere import moved
from absence.views import approvals, balances, calendar, payroll, requests, toil

app_name = "absence"
# Every leave page answers "leave is now in Shift Central" while SHIFT_CENTRAL_URL
# is set (absence/elsewhere.py); the payroll report is HR's own and stays.
urlpatterns = [
    path("request/", moved(requests.request_leave), name="request"),
    path("request/<int:pk>/", moved(requests.request_for), name="request_for"),
    path("mine/", moved(requests.mine), name="mine"),
    path("calendar/", moved(calendar.calendar_view), name="calendar"),
    path("balances/", moved(balances.balances_view), name="balances"),
    path("balances/team/", moved(balances.team), name="balances_team"),
    path("balances/<int:pk>/", moved(balances.balances_for), name="balances_for"),
    path("ledger/<int:pk>/", moved(balances.ledger_view), name="ledger"),
    path("payroll/", payroll.payroll_view, name="payroll"),
    path("queue/", moved(approvals.queue), name="queue"),
    # exactly notify.DECIDE_PATH: the link in the approver's email
    path("decide/<int:pk>/", moved(approvals.decide), name="decide"),
    path("toil/claim/", moved(toil.claim), name="toil_claim"),
    path("toil/claim/<int:pk>/", moved(toil.claim_for), name="toil_claim_for"),
    # exactly notify.CLAIM_DECIDE_PATH: the link in the approver's email
    path("toil/<int:pk>/decide/", moved(toil.decide), name="toil_decide"),
    path("toil/<int:pk>/cancel/", moved(toil.cancel), name="toil_cancel"),
    path("<int:pk>/cancel/", moved(requests.cancel), name="cancel"),
    path("<int:pk>/kit-day/", moved(requests.kit_day), name="kit_day"),
]
