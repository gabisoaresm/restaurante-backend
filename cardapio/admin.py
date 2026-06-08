from django.contrib import admin

from .models import Categoria, ItemCardapio


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    """Administração de categorias do cardápio."""

    list_display = ("nome",)
    search_fields = ("nome",)


@admin.register(ItemCardapio)
class ItemCardapioAdmin(admin.ModelAdmin):
    """Administração dos itens do cardápio com filtro por categoria e disponibilidade."""

    list_display = ("nome", "categoria", "preco", "disponivel")
    list_filter = ("categoria", "disponivel")
    search_fields = ("nome",)
