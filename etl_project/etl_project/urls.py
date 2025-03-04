
from django.contrib import admin
from django.urls import path, include  # ✅ Inclure "include" pour charger api_etl.urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api_etl.urls')),  # ✅ Charger les URLs de api_etl
]

