from django.contrib.auth import get_user_model
from rest_framework import serializers

from tenants.models import Business, TenantMembership

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "phone")


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    business_name = serializers.CharField(max_length=200)
    business_slug = serializers.SlugField(max_length=100)

    def validate_business_slug(self, value):
        if Business.objects.filter(slug=value).exists():
            raise serializers.ValidationError("This business slug is already in use.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )
        business = Business.objects.create(
            name=validated_data["business_name"],
            slug=validated_data["business_slug"],
            subdomain=validated_data["business_slug"],
        )
        TenantMembership.objects.create(
            user=user,
            business=business,
            role=TenantMembership.Role.OWNER_ADMIN,
        )
        return user