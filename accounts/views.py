"""
views.py — Views de autenticação do app accounts.

Endpoints implementados:
  POST   /api/accounts/registro/     → cria User + Perfil, retorna dados do usuário (201)
  POST   /api/accounts/token-auth/   → valida credenciais, retorna token (200)
  DELETE /api/accounts/token-auth/   → invalida o token atual, realiza logout (200)
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Perfil


class RegistroView(APIView):
    """
    Registra um novo usuário com perfil do tipo 'cliente' por padrão.

    POST → recebe username, password, email (opcional), first_name (opcional),
            last_name (opcional). Cria o User do Django e o Perfil associado.
            Retorna 201 com os dados do usuário criado, ou 400 se os dados
            forem inválidos (ex.: username já existe, senha em branco).
    """

    def post(self, request):
        """Cria um novo usuário e o Perfil com tipo 'cliente'."""
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")
        email = request.data.get("email", "").strip()
        first_name = request.data.get("first_name", "").strip()
        last_name = request.data.get("last_name", "").strip()

        # Validações básicas de entrada
        if not username or not password:
            return Response(
                {"erro": "username e password são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"erro": "Esse username já está em uso."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cria o usuário e o perfil dentro de uma operação atômica simples
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        Perfil.objects.create(usuario=user, tipo="cliente")

        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "tipo": "cliente",
            },
            status=status.HTTP_201_CREATED,
        )


class CustomAuthToken(APIView):
    """
    Gerencia o token de autenticação do usuário.

    POST   → valida username/password, gera (ou recupera) o token e retorna-o.
             Realiza login na sessão Django para compatibilidade com o admin.
             Retorna 200 com {'token': '...'} ou 401 se as credenciais forem inválidas.

    DELETE → lê o token do cabeçalho Authorization (formato: 'Token <valor>'),
             invalida o token no banco, realiza logout e retorna 200.
             Retorna 400 se o cabeçalho estiver ausente ou malformado.
    """

    def post(self, request):
        """Autentica o usuário e retorna o token de acesso."""
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response(
                {"erro": "Credenciais inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        login(request, user)

        return Response(
            {
                "token": token.key,
                "user_id": user.pk,
                "username": user.username,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        """Invalida o token do usuário e realiza logout."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Token "):
            return Response(
                {"erro": "Cabeçalho Authorization ausente ou inválido. Use: 'Token <seu_token>'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_key = auth_header.split(" ")[1]

        try:
            token = Token.objects.get(key=token_key)
        except Token.DoesNotExist:
            return Response(
                {"erro": "Token não encontrado ou já invalidado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token.delete()
        logout(request)

        return Response({"mensagem": "Logout realizado com sucesso."}, status=status.HTTP_200_OK)
