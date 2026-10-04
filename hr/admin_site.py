"""The admin site, and every value settings.UNFOLD reaches by dotted path.

settings.py never imports this module: unfold resolves the dotted strings
in UNFOLD with import_string at request time, which keeps the admin site
out of settings-import order entirely. Nothing here imports a model at
module level, for the same reason.
"""

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import redirect_to_login
from django.http import (HttpResponseForbidden, HttpResponseNotAllowed,
                         HttpResponseRedirect)
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from unfold.sites import UnfoldAdminSite


def is_hr_admin(request):
    """The one flag. Superusers are admitted regardless."""
    user = request.user
    return bool(user.is_active and (
        getattr(user, "is_hr_admin", False) or user.is_superuser))


def is_superuser(request):
    return bool(request.user.is_active and request.user.is_superuser)


class HrAdminSite(UnfoldAdminSite):
    site_title = "HR"
    site_header = "Practice HR"
    index_title = "Dashboard"

    def has_permission(self, request):
        return is_hr_admin(request)

    def _safe_next(self, request):
        target = request.GET.get("next", "")
        if target and url_has_allowed_host_and_scheme(
                target, allowed_hosts={request.get_host()},
                require_https=request.is_secure()):
            return target
        return reverse("admin:index")

    @method_decorator(never_cache)
    @login_not_required
    def login(self, request, extra_context=None):
        """One login page — the app's. A signed-in GP gets a 403 rather
        than a loop through a login form that would sign them in again."""
        if request.user.is_authenticated:
            if self.has_permission(request):
                return HttpResponseRedirect(self._safe_next(request))
            return HttpResponseForbidden("This account is not an HR admin.")
        return redirect_to_login(self._safe_next(request), settings.LOGIN_URL)

    @method_decorator(never_cache)
    def logout(self, request, extra_context=None):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        auth_logout(request)
        return HttpResponseRedirect(settings.LOGOUT_REDIRECT_URL)


# ---- values settings.UNFOLD reaches by dotted path ------------------------

def style_fonts(request):
    return static("css/fonts.css")


def style_admin(request):
    return static("admin/admin.css")


def _item(title, icon, link, permission=is_hr_admin):
    return {"title": title, "icon": icon, "link": link, "permission": permission}


def _nav_item(title, icon, url_name, permission=is_hr_admin):
    """None when `url_name` isn't registered yet. The People app's models
    (and their ModelAdmins) land one task at a time; without this, a nav
    entry for one not yet registered would raise NoReverseMatch on every
    admin page, not just its own."""
    try:
        link = reverse(url_name)
    except NoReverseMatch:
        return None
    return _item(title, icon, link, permission)


def navigation(request):
    groups = [
        {"title": "People", "separator": False, "items": [
            _nav_item("Employees", "badge", "admin:people_employee_changelist"),
            _nav_item("Employments", "work", "admin:people_employment_changelist"),
            _nav_item("Position titles", "work_outline", "admin:people_positiontitle_changelist"),
            _nav_item("Teams", "groups", "admin:people_team_changelist"),
            _nav_item("Contract types", "description", "admin:people_contracttype_changelist"),
            _nav_item("Audit log", "history", "admin:people_auditentry_changelist"),
        ]},
        {"title": "Absence", "separator": True, "items": [
            _nav_item("Absence types", "event_busy", "admin:absence_absencetype_changelist"),
            _nav_item("Policies", "policy", "admin:absence_policy_changelist"),
            _nav_item("Bank holidays", "flag", "admin:absence_bankholiday_changelist"),
            _nav_item("Closed days", "event_available", "admin:absence_closedday_changelist"),
            _nav_item("Pots", "savings", "admin:absence_pot_changelist"),
            _nav_item("Absences", "beach_access", "admin:absence_absence_changelist"),
            _nav_item("Payroll", "payments", "absence:payroll"),
            _nav_item("Retention", "auto_delete", "people:retention"),
        ]},
        {"title": "Compliance", "separator": True, "items": [
            _nav_item("Check types", "fact_check", "admin:checks_checktype_changelist"),
            _nav_item("Checks", "verified_user", "admin:checks_check_changelist"),
            _nav_item("Files", "folder", "admin:documents_file_changelist"),
            _nav_item("Policies", "policy", "admin:documents_policy_changelist"),
            _nav_item("Signatures", "draw", "admin:documents_signature_changelist"),
            _nav_item("Checklist templates", "checklist", "admin:onboarding_checklisttemplate_changelist"),
            _nav_item("Checklists", "task_alt", "admin:onboarding_checklist_changelist"),
            _nav_item("Starters and leavers", "how_to_reg", "onboarding:hr_list"),
            _nav_item("Reminder settings", "notifications", "admin:compliance_reminderschedule_changelist"),
        ]},
        {"title": "Access", "separator": True, "items": [
            _nav_item("Login accounts", "key", "admin:accounts_user_changelist"),
            _nav_item("Sign-in clients", "link", "admin:oauth2_provider_application_changelist",
                      permission=is_superuser),
        ]},
    ]
    if is_superuser(request):
        # The login lockout's record (docs/admin/sign-in.md), as in the rota.
        groups.append({"title": "System", "separator": True, "items": [
            _nav_item("Access attempts", "lock", "admin:axes_accessattempt_changelist",
                      permission=is_superuser),
            _nav_item("Access failures", "lock_open", "admin:axes_accessfailurelog_changelist",
                      permission=is_superuser),
            _nav_item("Access logs", "receipt_long", "admin:axes_accesslog_changelist",
                      permission=is_superuser),
        ]})
    for group in groups:
        group["items"] = [item for item in group["items"] if item is not None]
    return [group for group in groups if group["items"]]
