"""URLs principais do projeto restaurante_backend."""

from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="API do Restaurante",
        default_version="v1",
        description=(
            "API REST para o sistema de pedidos do restaurante. "
            "Permite gerenciar o cardápio, realizar pedidos e controlar "
            "o fluxo de preparo, com controle de acesso por perfil de usuário "
            "(gerente, atendente e cliente)."
        ),
        contact=openapi.Contact(email="contato@restaurante.local"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Documentação — Swagger UI e ReDoc
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

    # Endpoints da API
    path("api/cardapio/", include("cardapio.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/accounts/password_reset/", include("django_rest_passwordreset.urls", namespace="password_reset")),
    path("api/pedidos/", include("pedidos.urls")),
]
