"""URL configuration for the Mirror control-plane Django app.

The shipped dashboard surface is Django Admin. Host applications may include
this module under any prefix or replace it with their own URLconf that routes
``admin/`` to ``admin.site.urls``.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
