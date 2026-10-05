from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "onboarding"

    def ready(self):
        """Linked checklist items close themselves when the linked thing
        happens: a clear check recorded, a signature that leaves nothing
        owed, a file added for the person (onboarding.services.checklists)."""
        from checks.services import checks
        from documents.services import files, policies
        from onboarding.services import checklists
        for hooks, hook in ((checks.RECORDED_HOOKS, checklists.on_check_recorded),
                            (policies.SIGNED_HOOKS, checklists.on_policy_signed),
                            (files.ADDED_HOOKS, checklists.on_file_added)):
            if hook not in hooks:
                hooks.append(hook)
