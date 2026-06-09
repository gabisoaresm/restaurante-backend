"""
serializers.py — Serializers do app pedidos.

PedidoSerializer suporta criação aninhada: ao criar um pedido,
a lista de itens (ItemPedidoSerializer) é criada junto no mesmo request.
"""

from rest_framework import serializers

from .models import ItemPedido, Pedido


class ItemPedidoSerializer(serializers.ModelSerializer):
    """
    Serializer de um item dentro de um pedido.
    O campo 'item' recebe o id do ItemCardapio; 'quantidade' é a qtd solicitada.
    """

    class Meta:
        model = ItemPedido
        fields = ["id", "item", "quantidade"]


class PedidoSerializer(serializers.ModelSerializer):
    """
    Serializer completo de Pedido com suporte a criação aninhada de itens.

    Na leitura: inclui a lista de itens e o username do cliente.
    Na escrita (POST): espera 'itens' como lista de {item: id, quantidade: n}.
                       O campo 'cliente' é somente leitura — é preenchido pela view
                       a partir de request.user, nunca vindo do payload.
    """

    itens = ItemPedidoSerializer(many=True)
    cliente_username = serializers.CharField(source="cliente.username", read_only=True)

    class Meta:
        model = Pedido
        fields = [
            "id",
            "cliente",
            "cliente_username",
            "data_hora",
            "status",
            "forma_pagamento",
            "observacoes",
            "itens",
        ]
        read_only_fields = ["cliente", "data_hora", "status"]

    def create(self, validated_data):
        """Cria o Pedido e seus ItemPedido em cascata a partir dos dados validados."""
        itens_data = validated_data.pop("itens")
        pedido = Pedido.objects.create(**validated_data)
        for item_data in itens_data:
            ItemPedido.objects.create(pedido=pedido, **item_data)
        return pedido
