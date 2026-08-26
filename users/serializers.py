from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = CustomUser
        # 'role' deliberadamente ausente: novos usuários são sempre PATIENT.
        # Admins são criados apenas via Django admin por superusuário.
        fields = ('username', 'email', 'password', 'phone')

    def create(self, validated_data):
        user = CustomUser.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        # 'uid' é UUID público seguro; 'id' (PK sequencial) nunca exposto na API.
        fields = ('uid', 'username', 'email', 'role', 'phone', 'first_name', 'last_name')
        read_only_fields = ('uid', 'role')
