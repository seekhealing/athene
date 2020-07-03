from django.contrib.admin.apps import AdminConfig


class AtheneAdminConfig(AdminConfig):
    default_site = "athene.admin.AtheneAdminSite"
