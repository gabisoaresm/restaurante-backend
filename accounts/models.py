"""
models.py — Modelos de perfil de usuário e cartões salvos do restaurante.

Estende o User padrão do Django com:
  - Perfil: tipo de acesso (gerente, atendente, cliente).
  - CartaoSalvo: cartões de pagamento cadastrados pelo cliente.
"""

from django.contrib.auth.models import User
from django.db import models


class Perfil(models.Model):
    """
    Perfil estendido do usuário com o tipo de acesso no sistema.
    Relação OneToOne com User — deve ser criado junto com o registro do usuário.

    Tipos de acesso:
      - gerente:   CRUD completo do cardápio e visibilidade de todos os pedidos.
      - atendente: Visualiza e atualiza o status da fila de pedidos.
      - cliente:   Realiza pedidos e consulta apenas os próprios pedidos.
    """

    TIPO_CHOICES = [
        ("gerente", "Gerente"),
        ("atendente", "Atendente"),
        ("cliente", "Cliente"),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil",
        help_text="Usuário do Django associado a este perfil",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="cliente",
        help_text="Tipo de acesso do usuário no sistema",
    )

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        return f"{self.usuario.username} ({self.get_tipo_display()})"


class CartaoSalvo(models.Model):
    """
    Cartão de pagamento salvo pelo cliente para uso em pedidos futuros.
    Apenas os últimos 4 dígitos do número são armazenados (numero_mascarado).
    O CVV é guardado exclusivamente para verificação no momento do pedido.
    """

    BANDEIRA_CHOICES = [
        ("visa",       "Visa"),
        ("mastercard", "Mastercard"),
        ("elo",        "Elo"),
        ("amex",       "American Express"),
    ]
    TIPO_CHOICES = [
        ("credito", "Crédito"),
        ("debito",  "Débito"),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cartoes",
        help_text="Cliente dono do cartão",
    )
    apelido = models.CharField(
        max_length=50,
        help_text="Rótulo livre para identificar o cartão (ex.: Nubank, Visa final 1234)",
    )
    nome_titular = models.CharField(max_length=200, help_text="Nome impresso no cartão")
    numero_mascarado = models.CharField(
        max_length=19,
        help_text="Últimos 4 dígitos mascarados (ex.: **** **** **** 1234)",
    )
    bandeira = models.CharField(max_length=20, choices=BANDEIRA_CHOICES)
    tipo     = models.CharField(max_length=10, choices=TIPO_CHOICES)
    validade = models.CharField(max_length=7, help_text="MM/AAAA")
    cvv      = models.CharField(max_length=4, help_text="Código de segurança — verificado no pagamento")

    class Meta:
        ordering = ["apelido"]
        verbose_name = "Cartão Salvo"
        verbose_name_plural = "Cartões Salvos"

    def __str__(self):
        return f"{self.apelido} ({self.numero_mascarado})"
