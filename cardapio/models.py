"""
models.py — Modelos do cardápio do restaurante.

Estrutura:
    Categoria ──< ItemCardapio  (uma categoria agrupa vários itens)
"""

from django.db import models


class Categoria(models.Model):
    """
    Categoria dos itens do cardápio (ex: Entradas, Pratos Principais, Bebidas).
    Usada para agrupar e filtrar os itens exibidos ao cliente.
    """

    nome = models.CharField(max_length=100, help_text="Nome da categoria")

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nome


class ItemCardapio(models.Model):
    """
    Item disponível no cardápio do restaurante.
    Pertence a uma Categoria e pode ser marcado como indisponível
    sem precisar ser removido do banco — útil para sazonalidade ou falta de estoque.
    """

    nome = models.CharField(max_length=200, help_text="Nome do item")
    descricao = models.TextField(help_text="Descrição detalhada do item")
    preco = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Preço em reais",
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name="itens",
        help_text="Categoria à qual este item pertence",
    )
    disponivel = models.BooleanField(
        default=True,
        help_text="Indica se o item está disponível para pedido",
    )
    imagem = models.ImageField(
        upload_to="cardapio/",
        null=True,
        blank=True,
        help_text="Foto do item (opcional)",
    )

    class Meta:
        ordering = ["categoria", "nome"]
        verbose_name = "Item do Cardápio"
        verbose_name_plural = "Itens do Cardápio"

    def __str__(self):
        return f"{self.nome} ({self.categoria})"
