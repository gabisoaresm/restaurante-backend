"""
models.py — Modelos de pedidos do restaurante.

Estrutura:
    User ──< Pedido ──< ItemPedido >── ItemCardapio
    Pedido >──(opcional) CartaoSalvo
"""

from django.contrib.auth.models import User
from django.db import models

from accounts.models import CartaoSalvo
from cardapio.models import ItemCardapio


class Pedido(models.Model):
    """
    Pedido realizado por um cliente.
    Agrupa um ou mais ItemPedido e acompanha o ciclo de vida pelo campo status.

    Fluxo de status: recebido → em_preparo → pronto → entregue.
    Apenas o atendente/gerente pode avançar o status; o cliente só cria o pedido.
    """

    STATUS_CHOICES = [
        ("recebido", "Recebido"),
        ("em_preparo", "Em Preparo"),
        ("pronto", "Pronto"),
        ("entregue", "Entregue"),
    ]

    # Apenas pagamentos com cartão são aceitos; a forma é derivada do tipo do cartão selecionado
    FORMA_PAGAMENTO_CHOICES = [
        ("cartao_credito", "Cartão de Crédito"),
        ("cartao_debito",  "Cartão de Débito"),
    ]

    cliente = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pedidos",
        help_text="Cliente que realizou o pedido",
    )
    data_hora = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora em que o pedido foi registrado",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="recebido",
        help_text="Status atual do pedido no fluxo de preparo",
    )
    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_PAGAMENTO_CHOICES,
        help_text="Forma de pagamento escolhida pelo cliente",
    )
    observacoes = models.TextField(
        blank=True,
        default="",
        help_text="Observações adicionais do cliente sobre o pedido",
    )
    cartao_utilizado = models.ForeignKey(
        CartaoSalvo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pedidos",
        help_text="Cartão salvo usado no pagamento deste pedido",
    )

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.cliente.username} ({self.get_status_display()})"


class ItemPedido(models.Model):
    """
    Item individual dentro de um pedido.
    Liga um Pedido a um ItemCardapio com a quantidade solicitada.
    Acesso reverso a partir do Pedido: pedido.itens.all()
    """

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="itens",
        help_text="Pedido ao qual este item pertence",
    )
    item = models.ForeignKey(
        ItemCardapio,
        on_delete=models.CASCADE,
        help_text="Item do cardápio selecionado",
    )
    quantidade = models.PositiveIntegerField(
        default=1,
        help_text="Quantidade do item no pedido",
    )

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"

    def __str__(self):
        return f"{self.quantidade}x {self.item.nome} no Pedido #{self.pedido.pk}"
