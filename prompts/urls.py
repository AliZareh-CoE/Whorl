from django.urls import path

from . import views

app_name = "prompts"

urlpatterns = [
    path("prompts/", views.gallery, name="gallery"),
    path("prompts/new/", views.PromptCreateView.as_view(), name="create"),
    path("prompts/<int:pk>/edit/", views.PromptUpdateView.as_view(), name="edit"),
    path("prompts/<int:pk>/delete/", views.PromptDeleteView.as_view(), name="delete"),
]
