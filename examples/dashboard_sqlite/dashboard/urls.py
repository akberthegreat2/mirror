"""Project URL configuration: Django Admin is the dashboard."""
from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
