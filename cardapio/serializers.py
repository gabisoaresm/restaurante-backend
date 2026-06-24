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

    Campo extra write-only:
      remover_imagem — quando True no PUT, exclui a foto atual do item
                       (ignorado se uma nova imagem for enviada junto).
    """

    categoria_nome = serializers.CharField(source="categoria.nome", read_only=True)
    remover_imagem = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = ItemCardapio
        fields = [
            "id", "nome", "descricao", "preco",
            "categoria", "categoria_nome",
            "disponivel", "imagem",
            "remover_imagem",
        ]

    def update(self, instance, validated_data):
        """
        Sobrescreve update para suportar exclusão da imagem existente.
        Se remover_imagem=True e nenhuma imagem nova foi enviada, a foto é deletada do disco e do banco.
        Se uma imagem nova for enviada junto, ela substitui a atual normalmente (remover_imagem é ignorado).
        """
        remover = validated_data.pop("remover_imagem", False)
        nova_imagem = validated_data.get("imagem")

        if remover and not nova_imagem and instance.imagem:
            instance.imagem.delete(save=False)  # remove arquivo do disco
            instance.imagem = None              # limpa referência no banco

        return super().update(instance, validated_data)
