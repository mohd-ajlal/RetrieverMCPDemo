from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class LoginForm(AuthenticationForm):
    """Standard Django username/password login form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "Username", "autocomplete": "username", "class": "input"}
        )
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "Password",
                "autocomplete": "current-password",
                "class": "input",
            }
        )


class SignupForm(forms.Form):
    """Self-service registration: user + organization bootstrap."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "autocomplete": "username",
                "class": "input",
            }
        ),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Email (optional)",
                "autocomplete": "email",
                "class": "input",
            }
        ),
    )
    organization_name = forms.CharField(
        max_length=255,
        label="Organization name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Your organization",
                "class": "input",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "autocomplete": "new-password",
                "class": "input",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
                "class": "input",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_organization_name(self):
        name = self.cleaned_data["organization_name"].strip()
        if not name:
            raise forms.ValidationError("Organization name is required.")
        return name

    def clean_password1(self):
        password = self.cleaned_data.get("password1") or ""
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned
