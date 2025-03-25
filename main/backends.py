from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Custom authentication backend to login with email
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check if this is an email address
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing
            # attacks for non-existent users
            User().set_password(password)
            return None
