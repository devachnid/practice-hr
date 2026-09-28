from django import forms

from people.models import Contract, Employee, Employment, Position


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "preferred_name", "work_email", "personal_email",
                  "phone", "date_of_birth", "address_line1", "address_line2", "town", "postcode",
                  "ni_number", "user"]


class EmploymentForm(forms.ModelForm):
    class Meta:
        model = Employment
        fields = ["employee", "start_date", "end_date", "leaving_reason", "continuous_service_date"]


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "team", "line_manager", "primary", "from_date", "to_date"]


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ["contract_type", "basis", "from_date", "to_date", "weekly_amount", "notes"]
