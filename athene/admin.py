from django.contrib import admin

from seekers.admin_site import SeekersAdminSiteMixin
from events.admin_site import EventsAdminSiteMixin


class AtheneAdminSite(SeekersAdminSiteMixin, EventsAdminSiteMixin, admin.AdminSite):
    site_header = "SeekHealing - Athene"
    site_title = "SeekHealing Seekers Database"
    site_url = None
    index_title = "Seekers Database"
    login_template = "admin/admin_login.html"
