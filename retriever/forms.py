from __future__ import annotations

from django import forms

from retriever.models import DeploymentOrder, Device, ReturnOrder


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ("name", "device_type", "serial_number", "status")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "device_type": forms.TextInput(attrs={"class": "input"}),
            "serial_number": forms.TextInput(attrs={"class": "input"}),
            "status": forms.TextInput(attrs={"class": "input"}),
        }


class DeploymentOrderForm(forms.ModelForm):
    class Meta:
        model = DeploymentOrder
        fields = ("reference", "device", "status", "notes")
        widgets = {
            "reference": forms.TextInput(attrs={"class": "input"}),
            "device": forms.Select(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["device"].queryset = Device.objects.filter(
                organization=organization
            )
            self.fields["device"].required = False


class ReturnOrderForm(forms.ModelForm):
    class Meta:
        model = ReturnOrder
        fields = ("reference", "device", "status", "notes")
        widgets = {
            "reference": forms.TextInput(attrs={"class": "input"}),
            "device": forms.Select(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["device"].queryset = Device.objects.filter(
                organization=organization
            )
            self.fields["device"].required = False
