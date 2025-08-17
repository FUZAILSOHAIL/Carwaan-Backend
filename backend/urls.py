"""
URL configuration for backend projeurlpatterns = [
    path("admin/", admin.site.urls),  # Use default admin site
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.rides.urls")),
    path("api/", include("apps.core.urls")),  # Add core routing APIs
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),] `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.documentation import include_docs_urls
from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Carwaan API",
        default_version="v1",
        description="API documentation for Carwaan",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@carwaan.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),  # Use default admin site
    path("api/", include("apps.users.urls")),
    path("api/rides/", include("apps.rides.urls", namespace="rides")),
    path("api/routes/", include("apps.rides.api_urls", namespace="routes_api")),  # Route calculation API
    path("api/", include("apps.core.urls")),  # Add core routing APIs
    path("api/", include("apps.core.urls_upload")),  # Add upload endpoints
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # path("api/docs/", include_docs_urls(title="Carwaan API")),
]

# Add this line to serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
