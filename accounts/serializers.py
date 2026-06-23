"""
serializers.py — Serializers do app accounts.

CartaoSalvoSerializer: leitura/escrita de cartões salvos.
  - Escrita: recebe 'numero' (número completo); armazena apenas os últimos 4 dígitos
    mascarados em 'numero_mascarado'. O CVV é write-only — nunca exposto nas respostas.
  - Leitura: retorna id, apelido, nome_titular, numero_mascarado, bandeira, tipo, validade.
"""

import re

from rest_framework import serializers

from .models import CartaoSalvo


class CartaoSalvoSerializer(serializers.ModelSerializer):
    """
    Serializer de cartão salvo com mascaramento automático do número.

    Na escrita (POST): espera 'numero' com 13–19 dígitos (com ou sem espaços/hífens).
                       'cvv' é obrigatório e armazenado para verificação futura.
    Na leitura (GET):  retorna os campos públicos; 'cvv' é write-only (nunca exposto).
    """

    # Recebe o número completo do cartão; transformado em numero_mascarado no create()
    numero = serializers.CharField(write_only=True, max_length=19)

    class Meta:
        model = CartaoSalvo
        fields = [
            "id",
            "apelido",
            "nome_titular",
            "numero",
            "numero_mascarado",
            "bandeira",
            "tipo",
            "validade",
            "cvv",
        ]
        read_only_fields = ["numero_mascarado"]
        extra_kwargs = {
            "cvv": {"write_only": True},
        }

    def validate_numero(self, value):
        """Remove espaços/hífens e valida que o número tem entre 13 e 19 dígitos."""
        clean = re.sub(r"[\s\-]", "", value)
        if not clean.isdigit() or not (13 <= len(clean) <= 19):
            raise serializers.ValidationError(
                "Número do cartão inválido. Informe entre 13 e 19 dígitos."
            )
        return clean

    def validate_validade(self, value):
        """Valida o formato MM/AAAA."""
        if not re.match(r"^\d{2}/\d{4}$", value):
            raise serializers.ValidationError("Validade inválida. Use o formato MM/AAAA.")
        return value

    def create(self, validated_data):
        """Mascara os dígitos do número antes de persistir o cartão."""
        numero = validated_data.pop("numero")
        validated_data["numero_mascarado"] = f"**** **** **** {numero[-4:]}"
        return super().create(validated_data)
