from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("<slug:slug>/documents/", views.documents_index, name="index"),
    path("<slug:slug>/documents/upload/", views.DocumentCreateView.as_view(), name="upload"),
    path("<slug:slug>/documents/bulk-upload/", views.bulk_upload, name="bulk_upload"),
    path("<slug:slug>/documents/<int:pk>/rename/", views.document_rename, name="rename"),
    path("<slug:slug>/documents/<int:pk>/move/", views.document_move, name="move"),
    path(
        "<slug:slug>/documents/<int:pk>/edit/",
        views.DocumentUpdateView.as_view(),
        name="document_edit",
    ),
    path(
        "<slug:slug>/documents/<int:pk>/delete/",
        views.DocumentDeleteView.as_view(),
        name="document_delete",
    ),
    path("<slug:slug>/documents/<int:pk>/download/", views.document_download, name="download"),
    path(
        "<slug:slug>/documents/<int:pk>/suggest-tag/",
        views.add_suggested_tag,
        name="add_suggested_tag",
    ),
    path("<slug:slug>/folders/new/", views.FolderCreateView.as_view(), name="folder_create"),
    path(
        "<slug:slug>/folders/<int:pk>/edit/", views.FolderUpdateView.as_view(), name="folder_edit"
    ),
    path(
        "<slug:slug>/folders/<int:pk>/delete/",
        views.FolderDeleteView.as_view(),
        name="folder_delete",
    ),
    path("<slug:slug>/documents/bulk/", views.bulk_action, name="bulk"),
    path("<slug:slug>/tags/", views.tag_list, name="tags"),
    path("<slug:slug>/tags/new/", views.TagCreateView.as_view(), name="tag_create"),
    path("<slug:slug>/tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag_edit"),
    path("<slug:slug>/tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag_delete"),
]
