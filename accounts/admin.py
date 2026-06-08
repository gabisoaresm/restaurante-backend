from django.contrib import admin

from .models import Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    """Administração dos perfis de usuário (tipo de acesso)."""

    list_display = ("usuario", "tipo")
    list_filter = ("tipo",)
    search_fields = ("usuario__username",)
