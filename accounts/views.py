"""
views.py — Views de autenticação e cartões salvos do app accounts.

Endpoints implementados:
  POST   /api/accounts/registro/        → cria User + Perfil, retorna dados do usuário (201)
  POST   /api/accounts/token-auth/      → valida credenciais, retorna token (200)
  DELETE /api/accounts/token-auth/      → invalida o token atual, realiza logout (200)
  POST   /api/accounts/troca-senha/     → troca a senha do usuário autenticado e renova o token (200)
  GET    /api/accounts/me/              → retorna dados do usuário autenticado, incluindo tipo do perfil (200)
  PATCH  /api/accounts/me/              → atualiza first_name, last_name e email do usuário autenticado (200)
  GET    /api/accounts/cartoes/         → lista os cartões do cliente autenticado (200)
  POST   /api/accounts/cartoes/         → adiciona novo cartão ao cliente autenticado (201)
  GET    /api/accounts/cartoes/<id>/    → detalha um cartão do cliente (200)
  DELETE /api/accounts/cartoes/<id>/    → remove um cartão do cliente (204)
  GET    /api/accounts/usuarios/        → lista todos os usuários (somente gerente) (200)
  PATCH  /api/accounts/usuarios/<pk>/   → altera tipo de perfil de um usuário (somente gerente) (200)
  DELETE /api/accounts/usuarios/<pk>/   → remove um usuário do sistema (somente gerente) (204)

Recuperação de senha esquecida (django-rest-passwordreset):
  POST   /api/accounts/password_reset/          → solicita token de redefinição por e-mail
  POST   /api/accounts/password_reset/confirm/  → confirma nova senha usando o token recebido
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CartaoSalvo, Perfil
from .serializers import CartaoSalvoSerializer

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
            "Todos os campos são obrigatórios: `username`, `password`, `email`, `first_name` e `last_name`.\n\n"
            "O `email` deve ser único — não é permitido cadastrar dois usuários com o mesmo e-mail.\n\n"
            "A senha deve ter no mínimo 8 caracteres, não pode ser muito comum, "
            "não pode ser inteiramente numérica e não pode ser muito parecida com username ou e-mail."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["username", "password", "email", "first_name", "last_name"],
            properties={
                "username":   openapi.Schema(type=openapi.TYPE_STRING, description="Nome de usuário único"),
                "password":   openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description="Senha (mínimo 8 chars, não pode ser comum ou só numérica)"),
                "email":      openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description="E-mail único — necessário para recuperação de senha"),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="Nome"),
                "last_name":  openapi.Schema(type=openapi.TYPE_STRING, description="Sobrenome"),
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
        username   = request.data.get("username",   "").strip()
        password   = request.data.get("password",   "")
        email      = request.data.get("email",      "").strip().lower()
        first_name = request.data.get("first_name", "").strip()
        last_name  = request.data.get("last_name",  "").strip()

        # Todos os campos são obrigatórios
        if not username or not password or not email or not first_name or not last_name:
            return Response(
                {"erro": "Todos os campos são obrigatórios: username, password, email, first_name e last_name."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"erro": "Esse nome de usuário já está em uso."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica unicidade de e-mail (case-insensitive, como no Trabalho 1)
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"erro": "Já existe um usuário cadastrado com este e-mail."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida a senha usando os validators do Django (mínimo 8 chars, não comum, etc.)
        # Cria um objeto User temporário para que o UserAttributeSimilarityValidator
        # possa comparar a senha com username e email do novo usuário
        user_temp = User(username=username, email=email, first_name=first_name, last_name=last_name)
        try:
            validate_password(password, user=user_temp)
        except ValidationError as exc:
            return Response(
                {"erros": exc.messages},
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
    Retorna e atualiza os dados do usuário autenticado.

    GET   → exige token válido no cabeçalho Authorization.
            Retorna id, username, email, first_name, last_name, tipo e date_joined.
            Se o usuário não tiver Perfil associado, tipo é retornado como null.

    PATCH → atualiza first_name, last_name e email do usuário autenticado.
            Valida unicidade do e-mail (excluindo o próprio usuário).
            Retorna os dados atualizados.
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
                        "id":           openapi.Schema(type=openapi.TYPE_INTEGER),
                        "username":     openapi.Schema(type=openapi.TYPE_STRING),
                        "email":        openapi.Schema(type=openapi.TYPE_STRING),
                        "first_name":   openapi.Schema(type=openapi.TYPE_STRING),
                        "last_name":    openapi.Schema(type=openapi.TYPE_STRING),
                        "date_joined":  openapi.Schema(type=openapi.TYPE_STRING, description="Data de cadastro no formato dd/mm/aaaa"),
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
                "id":           request.user.pk,
                "username":     request.user.username,
                "email":        request.user.email,
                "first_name":   request.user.first_name,
                "last_name":    request.user.last_name,
                "date_joined":  request.user.date_joined.strftime("%d/%m/%Y"),
                "tipo":         tipo,
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Autenticação"],
        operation_summary="Atualizar perfil",
        operation_description=(
            "Atualiza os dados pessoais do usuário autenticado.\n\n"
            "Campos aceitos: `first_name`, `last_name`, `email`. "
            "O `email` deve ser único — não pode coincidir com outro usuário."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["first_name", "last_name", "email"],
            properties={
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="Nome"),
                "last_name":  openapi.Schema(type=openapi.TYPE_STRING, description="Sobrenome"),
                "email":      openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description="E-mail único"),
            },
        ),
        responses={
            200: openapi.Response("Dados atualizados com sucesso"),
            400: openapi.Response("Campos inválidos ou e-mail já cadastrado"),
            401: openapi.Response("Não autenticado — token ausente ou inválido"),
        },
    )
    def patch(self, request):
        """Atualiza os dados pessoais (first_name, last_name, email) do usuário autenticado."""
        user = request.user

        first_name = request.data.get("first_name", user.first_name).strip()
        last_name  = request.data.get("last_name",  user.last_name).strip()
        email      = request.data.get("email",      user.email).strip().lower()

        if not first_name or not last_name or not email:
            return Response(
                {"erro": "Os campos first_name, last_name e email são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica unicidade do e-mail excluindo o próprio usuário
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return Response(
                {"erro": "Já existe um usuário cadastrado com este e-mail."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.first_name = first_name
        user.last_name  = last_name
        user.email      = email
        user.save(update_fields=["first_name", "last_name", "email"])

        try:
            tipo = user.perfil.tipo
        except Exception:
            tipo = None

        return Response(
            {
                "id":           user.pk,
                "username":     user.username,
                "email":        user.email,
                "first_name":   user.first_name,
                "last_name":    user.last_name,
                "date_joined":  user.date_joined.strftime("%d/%m/%Y"),
                "tipo":         tipo,
            },
            status=status.HTTP_200_OK,
        )


class CartaoListView(APIView):
    """
    Lista os cartões salvos do cliente (GET) ou adiciona um novo cartão (POST).

    Ambos os métodos exigem autenticação por token e perfil 'cliente'.
    O campo 'usuario' é preenchido automaticamente com request.user.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Cartões"],
        operation_summary="Listar cartões salvos",
        operation_description="Retorna todos os cartões salvos do cliente autenticado.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: CartaoSalvoSerializer(many=True),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas clientes podem gerenciar cartões"),
        },
    )
    def get(self, request):
        """Lista os cartões do cliente autenticado."""
        try:
            tipo = request.user.perfil.tipo
        except Exception:
            tipo = None

        if tipo != "cliente":
            return Response(
                {"erro": "Apenas clientes podem gerenciar cartões."},
                status=status.HTTP_403_FORBIDDEN,
            )

        cartoes = CartaoSalvo.objects.filter(usuario=request.user)
        serializer = CartaoSalvoSerializer(cartoes, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cartões"],
        operation_summary="Adicionar cartão",
        operation_description=(
            "Salva um novo cartão para o cliente autenticado.\n\n"
            "Envie o número completo do cartão (13–19 dígitos); "
            "apenas os últimos 4 dígitos são armazenados mascarados. "
            "O CVV é armazenado exclusivamente para verificação no pagamento."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=CartaoSalvoSerializer,
        responses={
            201: CartaoSalvoSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas clientes"),
        },
    )
    def post(self, request):
        """Adiciona um novo cartão ao cliente autenticado."""
        try:
            tipo = request.user.perfil.tipo
        except Exception:
            tipo = None

        if tipo != "cliente":
            return Response(
                {"erro": "Apenas clientes podem adicionar cartões."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CartaoSalvoSerializer(data=request.data)
        if serializer.is_valid():
            # Associa o cartão ao cliente autenticado
            serializer.save(usuario=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartaoDetailView(APIView):
    """
    Recupera (GET) ou remove (DELETE) um cartão salvo pelo id.

    O cliente só pode acessar seus próprios cartões.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_cartao(self, pk, user):
        """Auxiliar: busca o cartão pelo pk garantindo que pertence ao usuário."""
        try:
            return CartaoSalvo.objects.get(pk=pk, usuario=user)
        except CartaoSalvo.DoesNotExist:
            return None

    @swagger_auto_schema(
        tags=["Cartões"],
        operation_summary="Detalhar cartão",
        operation_description="Retorna os dados de um cartão salvo pelo id.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: CartaoSalvoSerializer,
            401: openapi.Response("Não autenticado"),
            404: openapi.Response("Cartão não encontrado"),
        },
    )
    def get(self, request, pk):
        """Retorna os dados de um cartão do cliente autenticado."""
        cartao = self._get_cartao(pk, request.user)
        if cartao is None:
            return Response({"erro": "Cartão não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CartaoSalvoSerializer(cartao)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cartões"],
        operation_summary="Remover cartão",
        operation_description="Remove um cartão salvo pelo id. Apenas o dono pode remover.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            204: openapi.Response("Cartão removido com sucesso"),
            401: openapi.Response("Não autenticado"),
            404: openapi.Response("Cartão não encontrado"),
        },
    )
    def delete(self, request, pk):
        """Remove um cartão do cliente autenticado."""
        cartao = self._get_cartao(pk, request.user)
        if cartao is None:
            return Response({"erro": "Cartão não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        cartao.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuariosListView(APIView):
    """
    Lista todos os usuários cadastrados no sistema.

    Endpoint protegido: exige token de gerente.

    GET → retorna id, username, first_name, last_name, email, tipo e date_joined
          de todos os usuários com Perfil associado, ordenados por username.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Usuários"],
        operation_summary="Listar usuários",
        operation_description=(
            "Retorna todos os usuários cadastrados no sistema com seu tipo de perfil.\n\n"
            "Apenas gerentes podem acessar este endpoint."
        ),
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: openapi.Response(
                "Lista de usuários",
                openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "id":          openapi.Schema(type=openapi.TYPE_INTEGER),
                            "username":    openapi.Schema(type=openapi.TYPE_STRING),
                            "first_name":  openapi.Schema(type=openapi.TYPE_STRING),
                            "last_name":   openapi.Schema(type=openapi.TYPE_STRING),
                            "email":       openapi.Schema(type=openapi.TYPE_STRING),
                            "tipo":        openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                            "date_joined": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
            ),
            403: openapi.Response("Acesso negado — apenas gerentes"),
        },
    )
    def get(self, request):
        """Lista todos os usuários com seu tipo de perfil."""
        try:
            tipo_solicitante = request.user.perfil.tipo
        except Exception:
            tipo_solicitante = None

        if tipo_solicitante != "gerente":
            return Response(
                {"erro": "Apenas gerentes podem acessar a lista de usuários."},
                status=status.HTTP_403_FORBIDDEN,
            )

        usuarios = User.objects.select_related("perfil").order_by("username")
        resultado = []
        for u in usuarios:
            try:
                tipo_usuario = u.perfil.tipo
            except Exception:
                tipo_usuario = None

            resultado.append({
                "id":          u.pk,
                "username":    u.username,
                "first_name":  u.first_name,
                "last_name":   u.last_name,
                "email":       u.email,
                "tipo":        tipo_usuario,
                "date_joined": u.date_joined.strftime("%d/%m/%Y"),
            })

        return Response(resultado)


class UsuarioAlterarPerfilView(APIView):
    """
    Altera o tipo de perfil de um usuário específico.

    Endpoint protegido: exige token de gerente.

    PATCH → recebe {'tipo': 'cliente'|'atendente'|'gerente'} e atualiza
            o Perfil do usuário indicado pelo pk na URL.
            Cria o Perfil caso não exista (ex.: superusuário do Django admin).
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Usuários"],
        operation_summary="Alterar tipo de perfil",
        operation_description=(
            "Altera o tipo de perfil de um usuário. "
            "Apenas gerentes podem acessar este endpoint.\n\n"
            "Tipos válidos: `cliente`, `atendente`, `gerente`."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["tipo"],
            properties={
                "tipo": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Novo tipo de perfil: cliente, atendente ou gerente",
                ),
            },
        ),
        responses={
            200: openapi.Response("Perfil atualizado com sucesso"),
            400: openapi.Response("Tipo inválido"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Usuário não encontrado"),
        },
    )
    def patch(self, request, pk):
        """Atualiza o tipo de perfil do usuário indicado pelo pk."""
        try:
            tipo_solicitante = request.user.perfil.tipo
        except Exception:
            tipo_solicitante = None

        if tipo_solicitante != "gerente":
            return Response(
                {"erro": "Apenas gerentes podem alterar perfis de usuários."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            usuario = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"erro": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        novo_tipo = request.data.get("tipo", "").strip()
        tipos_validos = ["cliente", "atendente", "gerente"]
        if novo_tipo not in tipos_validos:
            return Response(
                {"erro": f"Tipo inválido. Use um dos valores: {', '.join(tipos_validos)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cria o Perfil se não existir (ex.: superusuário do Django admin sem perfil)
        perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
        perfil.tipo = novo_tipo
        perfil.save(update_fields=["tipo"])

        return Response({
            "id":          usuario.pk,
            "username":    usuario.username,
            "first_name":  usuario.first_name,
            "last_name":   usuario.last_name,
            "email":       usuario.email,
            "tipo":        novo_tipo,
            "date_joined": usuario.date_joined.strftime("%d/%m/%Y"),
        })

    @swagger_auto_schema(
        tags=["Usuários"],
        operation_summary="Excluir usuário",
        operation_description=(
            "Remove permanentemente um usuário do sistema.\n\n"
            "Apenas gerentes podem acessar este endpoint.\n\n"
            "O gerente não pode excluir a si mesmo."
        ),
        manual_parameters=[_AUTH_HEADER],
        responses={
            204: openapi.Response("Usuário excluído com sucesso"),
            400: openapi.Response("Operação não permitida (ex.: auto-exclusão)"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Usuário não encontrado"),
        },
    )
    def delete(self, request, pk):
        """Remove o usuário indicado pelo pk. Gerente não pode excluir a si mesmo."""
        try:
            tipo_solicitante = request.user.perfil.tipo
        except Exception:
            tipo_solicitante = None

        if tipo_solicitante != "gerente":
            return Response(
                {"erro": "Apenas gerentes podem excluir usuários."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.pk == pk:
            return Response(
                {"erro": "Você não pode excluir sua própria conta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usuario = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"erro": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        usuario.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
