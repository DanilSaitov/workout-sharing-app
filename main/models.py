from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

# Create your models here.

class User(AbstractUser):
    name = models.CharField(max_length=200, null=True)
    email = models.EmailField(unique=True, null=True)
    bio = models.TextField(null=True)
    avatar = models.ImageField(null=True, default="avatar.svg")
    profile_picture = models.ImageField(upload_to='profile_images/', null=True, blank=True)

    # Add related_name to avoid clashes with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='main_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='main_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # Username is required for AbstractUser

    class Meta:
        app_label = 'main'
        db_table = 'main_user'


# Workout Request Model here
class WorkoutRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_requests")
    date = models.DateField()
    time = models.TimeField()
    body_part = models.CharField(max_length=100)
    experience_level = models.CharField(max_length=50, choices=[('Beginner', 'Beginner'), ('Intermediate', 'Intermediate'), ('Advanced', 'Advanced')])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.body_part} on {self.date} at {self.time}"