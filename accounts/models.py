from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
	email = models.EmailField(unique=True)
	phone = models.CharField(max_length=20, blank=True)
	is_phone_verified = models.BooleanField(default=False)

	USERNAME_FIELD = "email"
	REQUIRED_FIELDS = ["username"]

	def __str__(self) -> str:
		return self.email

# Create your models here.
