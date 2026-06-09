"""URLs principais do projeto restaurante_backend."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/cardapio/", include("cardapio.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/pedidos/", include("pedidos.urls")),
]
