from django.urls import path

from . import views

app_name = "bots"

urlpatterns = [
    path("automations/", views.automations, name="automations"),
    path("automations/<slug:slug>/toggle/", views.toggle, name="toggle"),
    path("automations/<slug:slug>/run/", views.run_now, name="run_now"),
]
