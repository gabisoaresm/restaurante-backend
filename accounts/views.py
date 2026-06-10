"""
views.py — Views de autenticação do app accounts.

Endpoints implementados:
  POST   /api/accounts/registro/     → cria User + Perfil, retorna dados do usuário (201)
  POST   /api/accounts/token-auth/   → valida credenciais, retorna token (200)
  DELETE /api/accounts/token-auth/   → invalida o token atual, realiza logout (200)
  POST   /api/accounts/troca-senha/  → troca a senha do usuário autenticado e renova o token (200)
  GET    /api/accounts/me/           → retorna dados do usuário autenticado, incluindo tipo do perfil (200)

Recuperação de senha esquecida (django-rest-passwordreset):
  POST   /api/accounts/password_reset/          → solicita token de redefinição por e-mail
  POST   /api/accounts/password_reset/confirm/  → confirma nova senha usando o token recebido
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Perfil

# Parâmetro de cabeçalho de autenticação reutilizado nos endpoints protegidos
_AUTH_HEADER = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="Token de autenticação. Formato: Token <seu_token>",
    type=openapi.TYPE_STRING,
    required=True,
)


class RegistroView(APIView):
    """
    Registra um novo usuário com perfil do tipo 'cliente' por padrão.

    POST → recebe username, password, email (opcional), first_name (opcional),
            last_name (opcional). Cria o User do Django e o Perfil associado.
            Retorna 201 com os dados do usuário criado, ou 400 se os dados
            forem inválidos (ex.: username já existe, senha em branco).
    """

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Registrar novo usuário",
        operation_description=(
            "Cria um novo usuário com perfil do tipo **cliente**.\n\n"
            "Campos obrigatórios: `username` e `password`.\n"
            "Campos opcionais: `email`, `first_name`, `last_name`.\n\n"
            "**Dica:** informe o `email` — ele é necessário para recuperação de senha."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["username", "password"],
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING, description="Nome de usuário único"),
                "password": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Senha"),
                "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description="E-mail (necessário para recuperação de senha)"),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="Nome (opcional)"),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="Sobrenome (opcional)"),
            },
        ),
        responses={
            201: openapi.Response(
                "Usuário criado com sucesso",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "username": openapi.Schema(type=openapi.TYPE_STRING),
                        "email": openapi.Schema(type=openapi.TYPE_STRING),
                        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "tipo": openapi.Schema(type=openapi.TYPE_STRING, description="Sempre 'cliente' no registro"),
                    },
                ),
            ),
            400: openapi.Response("Dados inválidos — username já existe ou campos obrigatórios ausentes"),
        },
    )
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

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Login — obter token",
        operation_description=(
            "Autentica o usuário com `username` e `password`. "
            "Retorna o token de acesso a ser enviado no cabeçalho `Authorization` "
            "nas requisições subsequentes.\n\n"
            "**Como usar o token:** nas demais requisições protegidas, adicione o cabeçalho:\n"
            "`Authorization: Token <valor_retornado_aqui>`"
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["username", "password"],
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING, description="Nome de usuário"),
                "password": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Senha"),
            },
        ),
        responses={
            200: openapi.Response(
                "Login bem-sucedido",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "token": openapi.Schema(type=openapi.TYPE_STRING, description="Token de autenticação — use nas próximas requisições"),
                        "user_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "username": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            401: openapi.Response("Credenciais inválidas"),
        },
    )
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

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Logout — invalidar token",
        operation_description=(
            "Invalida o token do usuário autenticado e realiza logout.\n\n"
            "Envie o token no cabeçalho `Authorization` no formato `Token <seu_token>`."
        ),
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: openapi.Response("Logout realizado com sucesso"),
            400: openapi.Response("Cabeçalho Authorization ausente ou token inválido"),
        },
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


class TrocaSenhaView(APIView):
    """
    Troca a senha do usuário autenticado e renova o token de acesso.

    Endpoint protegido: exige token válido no cabeçalho Authorization.

    Fluxo:
      1. Recebe old_password, new_password1 e new_password2 no corpo da requisição.
      2. Verifica se old_password confere com a senha atual (check_password).
         Se não conferir → 400 com mensagem de erro.
      3. Verifica se new_password1 e new_password2 são iguais.
         Se não forem → 400 com mensagem de erro.
      4. Atualiza a senha com set_password e salva o usuário.
      5. Apaga o token antigo e gera um novo (renovação obrigatória após troca de senha).
      6. Retorna o novo token com HTTP 200.

    A renovação do token garante que sessões antigas (com o token anterior)
    sejam invalidadas imediatamente após a troca de senha.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Trocar senha",
        operation_description=(
            "Troca a senha do usuário autenticado e retorna um **novo token** de acesso.\n\n"
            "O token antigo é invalidado imediatamente após a troca. "
            "Use o novo token retornado nas requisições seguintes."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["old_password", "new_password1", "new_password2"],
            properties={
                "old_password": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Senha atual"),
                "new_password1": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Nova senha"),
                "new_password2": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Confirmação da nova senha"),
            },
        ),
        responses={
            200: openapi.Response(
                "Senha alterada com sucesso",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "mensagem": openapi.Schema(type=openapi.TYPE_STRING),
                        "token": openapi.Schema(type=openapi.TYPE_STRING, description="Novo token — use este nas próximas requisições"),
                    },
                ),
            ),
            400: openapi.Response("Senha atual incorreta ou novas senhas não coincidem"),
            401: openapi.Response("Não autenticado — token ausente ou inválido"),
        },
    )
    def post(self, request):
        """Valida a senha atual, aplica a nova e retorna um token renovado."""
        old_password = request.data.get("old_password", "")
        new_password1 = request.data.get("new_password1", "")
        new_password2 = request.data.get("new_password2", "")

        if not old_password or not new_password1 or not new_password2:
            return Response(
                {"erro": "Os campos old_password, new_password1 e new_password2 são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica se a senha atual está correta
        if not request.user.check_password(old_password):
            return Response(
                {"erro": "Senha atual incorreta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica se as duas novas senhas coincidem
        if new_password1 != new_password2:
            return Response(
                {"erro": "As novas senhas não coincidem."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Aplica a nova senha e salva o usuário
        request.user.set_password(new_password1)
        request.user.save()

        # Renova o token: apaga o antigo e gera um novo
        Token.objects.filter(user=request.user).delete()
        novo_token = Token.objects.create(user=request.user)

        return Response(
            {
                "mensagem": "Senha alterada com sucesso.",
                "token": novo_token.key,
            },
            status=status.HTTP_200_OK,
        )


class UsuarioAtualView(APIView):
    """
    Retorna os dados do usuário autenticado, incluindo o tipo do perfil.

    GET → exige token válido no cabeçalho Authorization.
          Retorna id, username, email, first_name, last_name e tipo do perfil.
          Se o usuário não tiver Perfil associado, tipo é retornado como null.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Usuário atual",
        operation_description=(
            "Retorna os dados do usuário autenticado pelo token informado.\n\n"
            "Útil para o frontend identificar o perfil do usuário após o login "
            "ou ao restaurar uma sessão existente."
        ),
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: openapi.Response(
                "Dados do usuário autenticado",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "username": openapi.Schema(type=openapi.TYPE_STRING),
                        "email": openapi.Schema(type=openapi.TYPE_STRING),
                        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "tipo": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Tipo do perfil: cliente, atendente ou gerente. null se não houver perfil.",
                            nullable=True,
                        ),
                    },
                ),
            ),
            401: openapi.Response("Não autenticado — token ausente ou inválido"),
        },
    )
    def get(self, request):
        """Retorna os dados e o tipo do perfil do usuário autenticado."""
        try:
            tipo = request.user.perfil.tipo
        except Exception:
            tipo = None

        return Response(
            {
                "id": request.user.pk,
                "username": request.user.username,
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "tipo": tipo,
            },
            status=status.HTTP_200_OK,
        )
