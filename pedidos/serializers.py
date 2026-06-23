"""
serializers.py — Serializers do app pedidos.

PedidoSerializer suporta criação aninhada com pagamento por cartão salvo:
  - Na escrita: espera 'cartao_id' (id de um CartaoSalvo do cliente) e 'cvv'
    para verificação. A 'forma_pagamento' é derivada automaticamente do tipo do cartão.
  - Na leitura: retorna todos os campos incluindo forma_pagamento e cliente_username.
"""

from rest_framework import serializers

from accounts.models import CartaoSalvo
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
    Serializer completo de Pedido com suporte a criação por cartão salvo.

    Na leitura: inclui a lista de itens e o username do cliente.
    Na escrita (POST): espera 'cartao_id' e 'cvv'.
                       Valida que o cartão pertence ao cliente e que o CVV está correto.
                       A 'forma_pagamento' é definida automaticamente (credito → cartao_credito).
                       O campo 'cliente' é preenchido pela view a partir de request.user.
    """

    itens = ItemPedidoSerializer(many=True)
    cliente_username = serializers.CharField(source="cliente.username", read_only=True)

    # Campos de pagamento write-only — usados na criação, não expostos nas respostas
    cartao_id = serializers.IntegerField(write_only=True)
    cvv       = serializers.CharField(write_only=True, max_length=4)

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
            "cartao_id",
            "cvv",
        ]
        read_only_fields = ["cliente", "data_hora", "status", "forma_pagamento"]

    def validate(self, data):
        """
        Valida o cartão e o CVV, e define forma_pagamento a partir do tipo do cartão.
        Depende de 'request' no contexto do serializer (passado pela view).
        """
        request = self.context.get("request")

        cartao_id = data.pop("cartao_id")
        cvv       = data.pop("cvv")

        # Verifica se o cartão pertence ao cliente autenticado
        try:
            cartao = CartaoSalvo.objects.get(pk=cartao_id, usuario=request.user)
        except CartaoSalvo.DoesNotExist:
            raise serializers.ValidationError(
                {"cartao_id": "Cartão não encontrado ou não pertence a este cliente."}
            )

        # Verifica o CVV informado contra o armazenado
        if cartao.cvv != cvv.strip():
            raise serializers.ValidationError({"cvv": "CVV incorreto."})

        # Valida que o pedido contém pelo menos um item
        if not data.get("itens"):
            raise serializers.ValidationError(
                {"itens": "O pedido deve conter pelo menos um item."}
            )

        # Deriva a forma de pagamento do tipo do cartão
        data["forma_pagamento"] = (
            "cartao_credito" if cartao.tipo == "credito" else "cartao_debito"
        )
        data["cartao_utilizado"] = cartao

        return data

    def create(self, validated_data):
        """Cria o Pedido e seus ItemPedido em cascata a partir dos dados validados."""
        itens_data = validated_data.pop("itens")
        pedido = Pedido.objects.create(**validated_data)
        for item_data in itens_data:
            ItemPedido.objects.create(pedido=pedido, **item_data)
        return pedido
