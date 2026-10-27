from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django import forms


class SaLinkAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'field__input',
            'autocomplete': 'username',
            'placeholder': 'Username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'field__input',
            'autocomplete': 'current-password',
            'placeholder': 'Password',
        })


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'username': 'Username',
            'email': 'nama@kampus.ac.id',
            'password1': 'Minimal 8 karakter',
            'password2': 'Ulangi password',
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'field__input',
                'placeholder': placeholders.get(field_name, ''),
            })


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'field__input'}),
            'last_name': forms.TextInput(attrs={'class': 'field__input'}),
            'email': forms.EmailInput(attrs={'class': 'field__input'}),
        }