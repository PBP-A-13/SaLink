from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from .models import UserProfile


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
    avatar = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'field__input', 'accept': 'image/*'}))

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'field__input'}),
            'first_name': forms.TextInput(attrs={'class': 'field__input'}),
            'last_name': forms.TextInput(attrs={'class': 'field__input'}),
            'email': forms.EmailInput(attrs={'class': 'field__input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile') and self.instance.profile.avatar:
            self.fields['avatar'].initial = self.instance.profile.avatar

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise ValidationError('Username tidak boleh kosong.')
        
        # Pastikan username unik kecuali untuk user itu sendiri
        exists = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists()
        if exists:
            raise ValidationError('Username ini sudah dipakai oleh pengguna lain. Silakan pilih username yang berbeda.')
        return username

    def save(self, commit=True):
        user = super().save(commit=commit)
        avatar = self.cleaned_data.get('avatar')
        if commit:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if avatar:
                profile.avatar = avatar
                profile.save()
        return user
