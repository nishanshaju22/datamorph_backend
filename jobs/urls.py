from django.urls import path
from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.JobDetailView.as_view(), name="detail"),
    path("<uuid:pk>/result/", views.JobResultView.as_view(), name="result"),
]