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

        serializer = PedidoSerializer(data=request.data)
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
