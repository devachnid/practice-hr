from django.contrib.admin.apps import AdminConfig


class HrAdminConfig(AdminConfig):
    """admin.site is our HrAdminSite (unfold, with the is_hr_admin rule)."""
    default_site = "hr.admin_site.HrAdminSite"
