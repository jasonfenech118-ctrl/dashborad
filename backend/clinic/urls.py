from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
