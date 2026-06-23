"""
views.py — Views de CRUD de pedidos com controle de acesso por tipo de perfil.

Todos os endpoints exigem autenticação por token (TokenAuthentication + IsAuthenticated).
A lógica de visibilidade e permissão é baseada em request.user.perfil.tipo:

  PedidoListView
    GET  → cliente: só os próprios pedidos.
           atendente/gerente: todos (com filtros opcionais ?status= e ?data=).
    POST → apenas cliente; o pedido é criado com cliente = request.user.

  PedidoDetailView
    GET   → cliente: só se o pedido for dele; atendente/gerente: qualquer um.
    PATCH → apenas atendente ou gerente; atualiza o status seguindo o fluxo:
            recebido → em_preparo → pronto → entregue.
    DELETE → apenas gerente pode excluir um pedido.

Fluxo de status válido: recebido → em_preparo → pronto → entregue.
Qualquer tentativa de pular ou regredir o status retorna HTTP 400.
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pedido
from .serializers import PedidoSerializer

# Mapeamento do próximo status válido no fluxo de preparo
PROXIMO_STATUS = {
    "recebido": "em_preparo",
    "em_preparo": "pronto",
    "pronto": "entregue",
}

# Parâmetro de cabeçalho de autenticação reutilizado em todos os endpoints
_AUTH_HEADER = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="Token de autenticação. Formato: Token <seu_token>",
    type=openapi.TYPE_STRING,
    required=True,
)


def _get_tipo(user):
    """Retorna o tipo do perfil do usuário, ou None se o perfil não existir."""
    try:
        return user.perfil.tipo
    except Exception:
        return None


class PedidoListView(APIView):
    """
    Lista os pedidos (GET) ou cria um novo pedido (POST).

    Ambos os métodos exigem autenticação por token.
    O comportamento do GET varia conforme o tipo de perfil do usuário autenticado.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Pedidos"],
        operation_summary="Listar pedidos",
        operation_description=(
            "Retorna pedidos filtrados conforme o perfil do usuário autenticado:\n\n"
            "- **cliente** → apenas os próprios pedidos.\n"
            "- **atendente** → todos os pedidos (fila de trabalho).\n"
            "- **gerente** → todos os pedidos.\n\n"
            "Filtros opcionais: `?status=recebido` e `?data=2025-06-09`."
        ),
        manual_parameters=[
            _AUTH_HEADER,
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filtra pedidos pelo status (recebido, em_preparo, pronto, entregue)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "data",
                openapi.IN_QUERY,
                description="Filtra pedidos pela data de criação (formato YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={
            200: PedidoSerializer(many=True),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Perfil inválido"),
        },
    )
    def get(self, request):
        """
        Retorna pedidos filtrados pelo tipo de perfil:
          - cliente   → apenas os próprios pedidos.
          - atendente → todos os pedidos (fila de trabalho), com filtros opcionais.
          - gerente   → todos os pedidos, com filtros opcionais.

        Query params opcionais: ?status=recebido&data=2025-06-09
        """
        tipo = _get_tipo(request.user)

        if tipo == "cliente":
            queryset = Pedido.objects.filter(cliente=request.user)
        elif tipo in ("atendente", "gerente"):
            queryset = Pedido.objects.all()
        else:
            return Response(
                {"erro": "Perfil de usuário inválido ou não encontrado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filtros opcionais por status e data (formato YYYY-MM-DD)
        filtro_status = request.query_params.get("status")
        filtro_data = request.query_params.get("data")

        if filtro_status:
            queryset = queryset.filter(status=filtro_status)
        if filtro_data:
            queryset = queryset.filter(data_hora__date=filtro_data)

        serializer = PedidoSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Pedidos"],
        operation_summary="Criar pedido",
        operation_description=(
            "Cria um novo pedido para o cliente autenticado.\n\n"
            "Apenas usuários com perfil **cliente** podem criar pedidos. "
            "O campo `cliente` é preenchido automaticamente com o usuário autenticado."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=PedidoSerializer,
        responses={
            201: PedidoSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas clientes podem criar pedidos"),
        },
    )
    def post(self, request):
        """
        Cria um novo pedido para o cliente autenticado.
        Apenas usuários com tipo 'cliente' podem criar pedidos.
        O campo 'cliente' é preenchido automaticamente com request.user.
        """
        tipo = _get_tipo(request.user)

        if tipo != "cliente":
            return Response(
                {"erro": "Apenas clientes podem criar pedidos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Passa o request no contexto para que o serializer possa verificar o cartão
        serializer = PedidoSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(cliente=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidoDetailView(APIView):
    """
    Recupera (GET), atualiza status (PATCH) ou remove (DELETE) um pedido pelo id.

    Todos os métodos exigem autenticação por token.
    O acesso é restrito conforme o tipo de perfil do usuário autenticado.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_pedido(self, pk):
        """Auxiliar: busca o pedido pelo pk ou retorna None."""
        try:
            return Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            return None

    @swagger_auto_schema(
        tags=["Pedidos"],
        operation_summary="Detalhar pedido",
        operation_description=(
            "Retorna os dados de um pedido pelo id.\n\n"
            "- **cliente** → só pode ver pedidos próprios (404 se tentar ver de outro cliente).\n"
            "- **atendente / gerente** → pode ver qualquer pedido."
        ),
        manual_parameters=[_AUTH_HEADER],
        responses={
            200: PedidoSerializer,
            401: openapi.Response("Não autenticado"),
            404: openapi.Response("Pedido não encontrado (ou não pertence ao cliente)"),
        },
    )
    def get(self, request, pk):
        """
        Retorna os dados de um pedido pelo id.
        Cliente só pode ver um pedido se ele for o dono;
        atendente e gerente podem ver qualquer pedido.
        """
        pedido = self._get_pedido(pk)
        if pedido is None:
            return Response({"erro": "Pedido não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        tipo = _get_tipo(request.user)

        if tipo == "cliente" and pedido.cliente != request.user:
            # Retorna 404 ao invés de 403 para não revelar a existência do pedido
            return Response({"erro": "Pedido não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PedidoSerializer(pedido)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Pedidos"],
        operation_summary="Atualizar status do pedido",
        operation_description=(
            "Avança o status de um pedido seguindo o fluxo obrigatório:\n\n"
            "`recebido` → `em_preparo` → `pronto` → `entregue`\n\n"
            "Apenas **atendente** ou **gerente** podem alterar o status. "
            "Retorna 400 se o status enviado não for o próximo válido no fluxo."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["em_preparo", "pronto", "entregue"],
                    description="Próximo status no fluxo de preparo",
                )
            },
        ),
        responses={
            200: PedidoSerializer,
            400: openapi.Response("Status inválido ou pedido já entregue"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas atendentes e gerentes"),
            404: openapi.Response("Pedido não encontrado"),
        },
    )
    def patch(self, request, pk):
        """
        Atualiza o status de um pedido seguindo o fluxo obrigatório:
        recebido → em_preparo → pronto → entregue.

        Apenas atendente ou gerente podem alterar o status.
        Retorna 400 se o status enviado não for o próximo válido no fluxo.
        """
        tipo = _get_tipo(request.user)

        if tipo not in ("atendente", "gerente"):
            return Response(
                {"erro": "Apenas atendentes e gerentes podem atualizar o status do pedido."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pedido = self._get_pedido(pk)
        if pedido is None:
            return Response({"erro": "Pedido não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        novo_status = request.data.get("status")
        proximo_valido = PROXIMO_STATUS.get(pedido.status)

        if proximo_valido is None:
            return Response(
                {"erro": "Este pedido já foi entregue e não pode ser atualizado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if novo_status != proximo_valido:
            return Response(
                {
                    "erro": f"Status inválido. O próximo status permitido é '{proximo_valido}'.",
                    "status_atual": pedido.status,
                    "proximo_permitido": proximo_valido,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedido.status = novo_status
        pedido.save()
        serializer = PedidoSerializer(pedido)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Pedidos"],
        operation_summary="Remover pedido",
        operation_description="Remove um pedido pelo id. Apenas **gerentes** podem excluir pedidos.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            204: openapi.Response("Pedido removido com sucesso"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Pedido não encontrado"),
        },
    )
    def delete(self, request, pk):
        """
        Remove um pedido pelo id.
        Apenas gerentes podem excluir pedidos.
        """
        tipo = _get_tipo(request.user)

        if tipo != "gerente":
            return Response(
                {"erro": "Apenas gerentes podem excluir pedidos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pedido = self._get_pedido(pk)
        if pedido is None:
            return Response({"erro": "Pedido não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        pedido.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
