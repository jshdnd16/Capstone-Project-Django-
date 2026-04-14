# accounts/forms.py
# Django forms handle both HTML rendering AND data validation.
# When a form is submitted, Django validates the data here
# before it ever reaches the view or the database.

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Role


class LoginForm(forms.Form):
    """
    Simple login form with username and password fields.
    We use a plain Form (not ModelForm) since we're just 
    checking credentials, not creating/editing a record.
    """

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',           # CSS class for styling
            'placeholder': 'Enter username',
            'autofocus': True,               # Automatically focus this field on page load
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter password',
        })
    )


class UserCreateForm(UserCreationForm):
    """
    Form for Admin to create new user accounts.
    Extends Django's UserCreationForm which handles the 
    password + confirm password fields automatically.
    """

    # Add our custom fields to the form
    fullname = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'})
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email (optional)'})
    )

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text="Assign a role to control what this user can access"
    )

    department = forms.ChoiceField(
        choices=User.DEPARTMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = User
        fields = ['username', 'fullname', 'email', 'role', 'department',
                  'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to the password fields that come from UserCreationForm
        self.fields['username'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Login username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm password'
        })

    def clean_username(self):
        """
        Custom validation: usernames must be lowercase letters, numbers, underscores.
        This runs automatically when form.is_valid() is called.
        """
        username = self.cleaned_data.get('username', '').strip().lower()
        return username


class UserEditForm(forms.ModelForm):
    """
    Form for Admin to edit an existing user account.
    Note: Password is NOT included here — use Django's built-in
    password change view for that.
    """

    class Meta:
        model = User
        fields = ['fullname', 'email', 'role', 'department', 'status']
        widgets = {
            'fullname':   forms.TextInput(attrs={'class': 'form-input'}),
            'email':      forms.EmailInput(attrs={'class': 'form-input'}),
            'role':       forms.Select(attrs={'class': 'form-input'}),
            'department': forms.Select(attrs={'class': 'form-input'}),
            'status':     forms.Select(attrs={'class': 'form-input'}),
        }