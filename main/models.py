from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import Q, Count, Case, When

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
    max_participants = models.PositiveIntegerField(default=2, validators=[MinValueValidator(2)])
    current_participants = models.IntegerField(default=1)
    is_full = models.BooleanField(default=False)
    is_past = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updating_participants = models.BooleanField(default=False)
    
    def update_participant_count(self):
        """Update the participant count and full status"""
        if self.updating_participants:
            return
        
        self.updating_participants = True
        # Calculate new values
        new_count = self.workout_invitations.filter(Q(status='accepted') | Q(status='completed')).count() + 1
        new_is_full = new_count >= self.max_participants
        
        # Only update if values have changed
        if self.current_participants != new_count or self.is_full != new_is_full:
            self.current_participants = new_count
            self.is_full = new_is_full
            self.save(update_fields=['current_participants', 'is_full'])
        
        self.updating_participants = False
    
    def save(self, *args, **kwargs):
        # Set initial values for new instances
        if not self.pk:
            self.current_participants = 1  # Start with creator
            self.is_full = False
            self.is_past = False
        
        # Update values for existing instances
        if self.pk:
            self.is_past = timezone.now() > timezone.make_aware(timezone.datetime.combine(self.date, self.time))
            self.update_participant_count()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.body_part} on {self.date} at {self.time}"

# Friend Request Model
class FriendRequest(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='friend_requests_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='friend_requests_received', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('from_user', 'to_user')
        
    def __str__(self):
        return f"{self.from_user.username} to {self.to_user.username}"

# Friendship Model
class Friendship(models.Model):
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='friendships', on_delete=models.CASCADE)
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='friend_of', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user1', 'user2')
        
    def __str__(self):
        return f"{self.user1.username} and {self.user2.username}"

# Message Model for Private Messaging
class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Workout Invitation Model
class WorkoutInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    ]
    
    workout_request = models.ForeignKey(WorkoutRequest, on_delete=models.CASCADE, related_name='workout_invitations')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_workout_invitations', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_workout_invitations', on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='workout_invitation', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def cancel(self, user):
        """Cancel this invitation and notify the other party"""
        if user == self.sender:
            self.status = 'cancelled'
            Message.objects.create(
                sender=user,
                receiver=self.receiver,
                content=f"I've cancelled our workout on {self.workout_request.date}"
            )
        else:
            self.status = 'declined'
            Message.objects.create(
                sender=user,
                receiver=self.sender,
                content=f"I can't attend the workout on {self.workout_request.date}"
            )
        self.save()
        # Update the participant count after cancellation
        self.workout_request.update_participant_count()

    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.workout_request.body_part} ({self.status})"

# Activity Feed Model
class ActivityFeed(models.Model):
    ACTIVITY_TYPES = [
        ('workout_created', 'Workout Created'),
        ('workout_cancelled', 'Workout Cancelled'),
        ('workout_deleted', 'Workout Deleted'),
        ('friend_request', 'Friend Request'),
        ('friend_added', 'Friend Added'),
        ('message_received', 'Message Received'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    message = models.TextField()
    related_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_activities')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# User Settings Model
class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_settings')
    show_friend_activities = models.BooleanField(default=True)
    show_workout_activities = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Settings for {self.user.username}"

# Workout Stats Model
class WorkoutStats(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workout_stats')
    total_workouts = models.IntegerField(default=0)
    completed_workouts = models.IntegerField(default=0)
    cancelled_workouts = models.IntegerField(default=0)
    body_parts_stats = models.JSONField(default=dict)  # {'chest': 5, 'legs': 3, etc.}
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Workout stats for {self.user.username}"
    
    def update_stats(self):
        """Update workout statistics for the user"""
        # Count total workouts (both created and participated)
        created = WorkoutRequest.objects.filter(user=self.user).count()
        participated = WorkoutInvitation.objects.filter(
            receiver=self.user, 
            status__in=['accepted', 'completed']
        ).count()
        
        self.total_workouts = created + participated
        
        # Count completed workouts
        completed_created = WorkoutRequest.objects.filter(
            user=self.user, 
            is_past=True
        ).count()
        
        completed_participated = WorkoutInvitation.objects.filter(
            receiver=self.user, 
            status='completed'
        ).count()
        
        self.completed_workouts = completed_created + completed_participated
        
        # Count cancelled workouts
        cancelled_created = WorkoutRequest.objects.filter(
            user=self.user, 
            workout_invitations__status='cancelled'
        ).count()
        
        cancelled_participated = WorkoutInvitation.objects.filter(
            receiver=self.user, 
            status='cancelled'
        ).count()
        
        self.cancelled_workouts = cancelled_created + cancelled_participated
        
        # Calculate body part stats
        body_parts = {}
        
        # From created workouts
        for part in WorkoutRequest.objects.filter(user=self.user).values('body_part').annotate(count=Count('body_part')):
            body_parts[part['body_part']] = part['count']
        
        # From participated workouts
        for part in WorkoutInvitation.objects.filter(
            receiver=self.user, 
            status__in=['accepted', 'completed']
        ).values('workout_request__body_part').annotate(count=Count('workout_request__body_part')):
            part_name = part['workout_request__body_part']
            body_parts[part_name] = body_parts.get(part_name, 0) + part['count']
        
        self.body_parts_stats = body_parts
        self.save()