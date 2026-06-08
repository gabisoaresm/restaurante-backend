from django.contrib import admin

from .models import ItemPedido, Pedido


class ItemPedidoInline(admin.TabularInline):
    """Itens do pedido exibidos inline dentro do painel de Pedido."""

    model = ItemPedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    """Administração dos pedidos com visualização dos itens inline."""

    list_display = ("pk", "cliente", "status", "forma_pagamento", "data_hora")
    list_filter = ("status", "forma_pagamento")
    search_fields = ("cliente__username",)
    inlines = [ItemPedidoInline]


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    """Administração individual dos itens de pedido."""

    list_display = ("pedido", "item", "quantidade")
