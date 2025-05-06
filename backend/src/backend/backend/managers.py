from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _

class TibavaUserManager(BaseUserManager):
    def create_user(self, username, email, password):
        email = self.normalize_email(email)
        user = self.model(username=username, email=email)
        user.set_password(password)
        user.save()
        return user