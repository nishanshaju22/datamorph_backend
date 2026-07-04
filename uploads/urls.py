from django.urls import path
from . import views

app_name = "uploads"

urlpatterns = [
    path("", views.UploadListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.UploadDetailView.as_view(), name="detail"),
]