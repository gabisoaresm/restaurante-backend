"""
signals.py — Receptor de sinal para recuperação de senha via django-rest-passwordreset.

Quando o pacote django_rest_passwordreset gera um token de redefinição, ele dispara o
sinal `reset_password_token_created`. Este módulo escuta esse sinal e envia o e-mail
com o token para o usuário, usando templates HTML e texto simples.
"""

from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver
from django.template.loader import render_to_string
from django_rest_passwordreset.signals import reset_password_token_created


@receiver(reset_password_token_created)
def enviar_email_redefinicao_senha(sender, instance, reset_password_token, *args, **kwargs):
    """
    Envia o e-mail de redefinição de senha quando o sinal reset_password_token_created
    é disparado pelo pacote django-rest-passwordreset.

    Parâmetros recebidos do sinal:
      - sender: a view que disparou o sinal
      - instance: a instância da view
      - reset_password_token: objeto com .key (token) e .user (usuário solicitante)

    O e-mail é enviado em duas partes (multipart/alternative):
      - texto simples (fallback para clientes sem suporte a HTML)
      - HTML formatado (exibido por clientes modernos)
    """
    contexto = {
        "user": reset_password_token.user,
        "reset_password_token": reset_password_token,
    }

    corpo_texto = render_to_string("accounts/email/password_reset_email.txt", contexto)
    corpo_html = render_to_string("accounts/email/password_reset_email.html", contexto)

    email = EmailMultiAlternatives(
        subject="Redefinição de Senha — Restaurante",
        body=corpo_texto,
        to=[reset_password_token.user.email],
    )
    email.attach_alternative(corpo_html, "text/html")
    email.send()
