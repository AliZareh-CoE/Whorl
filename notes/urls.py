from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/<int:pk>/triage/", views.triage, name="triage"),
]
