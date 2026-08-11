"""
URL configuration for API app endpoints.
"""

from django.urls import path
from api.views import (
    ChatView,
    DocumentIngestView,
    DocumentListView,
    HealthCheckView,
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='api-health'),
    path('ingest/', DocumentIngestView.as_view(), name='api-ingest'),
    path('documents/', DocumentListView.as_view(), name='api-documents'),
    path('chat/', ChatView.as_view(), name='api-chat'),
]
