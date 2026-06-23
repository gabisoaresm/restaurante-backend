from django.contrib import admin

from .models import CartaoSalvo, Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    """Administração dos perfis de usuário (tipo de acesso)."""

    list_display = ("usuario", "tipo")
    list_filter = ("tipo",)
    search_fields = ("usuario__username",)


@admin.register(CartaoSalvo)
class CartaoSalvoAdmin(admin.ModelAdmin):
    """Administração dos cartões salvos dos clientes."""

    list_display = ("usuario", "apelido", "numero_mascarado", "bandeira", "tipo", "validade")
    list_filter = ("bandeira", "tipo")
    search_fields = ("usuario__username", "apelido", "nome_titular")
