from django import forms

from services.models import Service
from staffs.models import Employee


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "description", "duration_minutes", "price", "is_active"]


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "telegram_username",
            "telegram_chat_id",
            "title",
            "is_active",
        ]
