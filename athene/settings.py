"""
Django settings for athene project.

Generated by 'django-admin startproject' using Django 2.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import json

import dj_database_url


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "0p3ns3s4m3!#")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get("DEBUG", ""))

ALLOWED_HOSTS = [] if DEBUG else ["seekers.seekhealing.org", "seekhealing-athene.herokuapp.com"]


# Application definition

INSTALLED_APPS = [
    # 'django.contrib.admin',
    "athene.apps.AtheneAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "localflavor.us",
    "phonenumber_field",
    "ckeditor",
    "seekers",
    "events",
]
if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if DEBUG:
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware",)

ROOT_URLCONF = "athene.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "athene.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.config(env="DATABASE_URL", default="postgres://athene:athene@127.0.0.1:5432/athene")
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "US/Eastern"

USE_I18N = False

USE_L10N = False

USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}},
    "handlers": {
        "default": {"level": "DEBUG" if DEBUG else "INFO", "formatter": "standard", "class": "logging.StreamHandler"},
    },
    "loggers": {
        "athene": {"handlers": ["default"], "level": "DEBUG"},
        "seekers": {"handlers": ["default"], "level": "DEBUG"},
        "events": {"handlers": ["default"], "level": "DEBUG"},
        "celery.tasks": {"handlers": ["default"], "level": "DEBUG"},
    },
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = "/static/"

PHONENUMBER_DB_FORMAT = "NATIONAL"
PHONENUMBER_DEFAULT_REGION = "US"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

INTERNAL_IPS = ["127.0.0.1"]

CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "Custom",
        "toolbar_Custom": [
            ["Bold", "Italic", "Underline"],
            ["NumberedList", "BulletedList"],
            ["Link", "Unlink"],
            ["RemoveFormat", "Source"],
        ],
        "allowedContent": "p b strong i em u ul ol li a[!href]",
    }
}

GOOGLEMAPS_API = os.environ.get("GOOGLEMAPS_API", None)

MAILCHIMP_API_KEY = os.environ.get("MAILCHIMP_API_KEY")
MAILCHIMP_USERNAME = os.environ.get("MAILCHIMP_USERNAME")
MAILCHIMP_LIST_ID = os.environ.get("MAILCHIMP_LIST_ID")

MAILCHIMP_TAGS = json.loads(os.environ.get("MAILCHIMP_TAGS", "[]"))
MAILCHIMP_DEFAULT_HUMAN_TAGS = json.loads(os.environ.get("MAILCHIMP_DEFAULT_HUMAN_TAGS", "[]"))
MAILCHIMP_DEFAULT_SEEKER_TAGS = json.loads(os.environ.get("MAILCHIMP_DEFAULT_SEEKER_TAGS", "[]"))
MAILCHIMP_DEFAULT_COMMUNITYPARTNER_TAGS = json.loads(os.environ.get("MAILCHIMP_DEFAULT_COMMUNITYPARTNER_TAGS", "[]"))

if "SENTRY_DSN" in os.environ:
    import sentry_sdk  # noqa: E402
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], integrations=[DjangoIntegration()])

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True

EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("MAILGUN_SMTP_SERVER", "")
EMAIL_PORT = os.environ.get("MAILGUN_SMTP_PORT", "")
EMAIL_HOST_USER = os.environ.get("MAILGUN_SMTP_LOGIN", "")
EMAIL_HOST_PASSWORD = os.environ.get("MAILGUN_SMTP_PASSWORD", "")
DEFAULT_FROM_EMAIL = "athene@seekers.seekhealing.org"


CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")
