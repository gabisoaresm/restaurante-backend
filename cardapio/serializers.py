"""
serializers.py — Serializers do app cardapio.

Convertem instâncias de Categoria e ItemCardapio para/de JSON,
validando os dados recebidos nas requisições POST/PUT.
"""

from rest_framework import serializers

from .models import Categoria, ItemCardapio


class CategoriaSerializer(serializers.ModelSerializer):
    """Serializer completo de Categoria — usado em listagem e detalhe."""

    class Meta:
        model = Categoria
        fields = ["id", "nome"]


class ItemCardapioSerializer(serializers.ModelSerializer):
    """
    Serializer completo de ItemCardapio.
    Expõe o nome da categoria como campo de leitura (categoria_nome)
    além do id da FK (categoria) usado na escrita.
    """

    categoria_nome = serializers.CharField(source="categoria.nome", read_only=True)

    class Meta:
        model = ItemCardapio
        fields = ["id", "nome", "descricao", "preco", "categoria", "categoria_nome", "disponivel"]
