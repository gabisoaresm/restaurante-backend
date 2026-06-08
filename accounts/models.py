"""
models.py — Modelo de perfil de usuário do restaurante.

Estende o User padrão do Django com um campo de tipo,
que determina as permissões de acesso em toda a API.
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
