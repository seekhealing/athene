from django.conf import settings
from django.contrib.auth import backends


class SuperUserOnlyModelBackend(backends.ModelBackend):
    def user_can_authenticate(self, user):
        return user.is_active and (settings.DEBUG or user.is_superuser)
