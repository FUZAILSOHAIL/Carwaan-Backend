# apps/core/urls_upload.py
from django.urls import path
from . import views_upload

urlpatterns = [
    # ZIP file upload endpoints
    path('upload-zip/', views_upload.upload_zip_file, name='upload_zip_file'),
    path('uploaded-files/', views_upload.list_uploaded_files, name='list_uploaded_files'),
    path('uploaded-files/<str:filename>/delete/', views_upload.delete_uploaded_file, name='delete_uploaded_file'),
]
