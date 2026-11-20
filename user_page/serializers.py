from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(
        source='profile.avatar',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'avatar',
        ]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})

        instance = super().update(instance, validated_data)

        if 'avatar' in profile_data:
            profile, _ = UserProfile.objects.get_or_create(
                user=instance
            )
            profile.avatar = profile_data['avatar']
            profile.save()

        return instance
