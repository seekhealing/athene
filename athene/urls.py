"""athene URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, re_path, include

from seekers import views

robots_txt = HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")
robots_txt["Cache-Control"] = "max-age=1209600"
index = HttpResponseRedirect("https://seekhealing.org/")
index["Cache-Control"] = "max-age=1209600"

urlpatterns = [
    path("admin_tools/", include("admin_tools.urls")),
    path("admin/", admin.site.urls),
    re_path("^robots.txt$", lambda r: robots_txt),
    path("webhooks/mailgun/", views.mailgun_webhook),
    path("webhooks/twilio/", views.twilio_webhook),
    path("auth/", include("social_django.urls", namespace="social")),
    path("", lambda r: index),
]

if settings.DEBUG:
    try:
        import debug_toolbar  # noqa
    except ImportError:
        pass
    else:
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
