"""
views.py — Views de CRUD do cardápio (Categoria e ItemCardapio).

Padrão adotado (conforme slides da disciplina):
  - CategoriaListView    → GET /categorias/        (público)    POST /categorias/      (gerente)
  - CategoriaDetailView  → GET /categorias/<id>/   (público)    PUT /categorias/<id>/  (gerente)  DELETE /categorias/<id>/ (gerente)
  - ItemCardapioListView   → GET /itens/            (público)    POST /itens/           (gerente)
  - ItemCardapioDetailView → GET /itens/<id>/       (público)    PUT /itens/<id>/       (gerente)  DELETE /itens/<id>/      (gerente)

Leitura (GET) é pública — qualquer um pode consultar o cardápio sem autenticação.
Escrita (POST, PUT, DELETE) exige token válido e perfil do tipo 'gerente'.

Itens do cardápio aceitam upload de imagem via multipart/form-data.
O campo imagem é opcional (null=True, blank=True no model).
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Categoria, ItemCardapio
from .serializers import CategoriaSerializer, ItemCardapioSerializer

# Parâmetro de cabeçalho de autenticação reutilizado em todos os endpoints protegidos
_AUTH_HEADER = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="Token de autenticação. Formato: Token <seu_token>",
    type=openapi.TYPE_STRING,
    required=True,
)

# Schema do corpo multipart para POST/PUT de itens (inclui campo de imagem)
_ITEM_FORM_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["nome", "descricao", "preco", "categoria"],
    properties={
        "nome":      openapi.Schema(type=openapi.TYPE_STRING, description="Nome do item"),
        "descricao": openapi.Schema(type=openapi.TYPE_STRING, description="Descrição detalhada"),
        "preco":     openapi.Schema(type=openapi.TYPE_NUMBER, description="Preço em reais"),
        "categoria": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID da categoria"),
        "disponivel": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Disponível para pedido (padrão: true)"),
        "imagem":    openapi.Schema(type=openapi.TYPE_FILE, description="Foto do item (opcional)"),
    },
)


def _checar_gerente(request):
    """
    Verifica se o request vem de um usuário autenticado com perfil 'gerente'.
    Retorna None se a verificação passar, ou uma Response de erro caso contrário:
      401 — sem autenticação.
      403 — autenticado, mas não é gerente.
    """
    if not request.user or not request.user.is_authenticated:
        return Response(
            {"erro": "Autenticação necessária. Envie o cabeçalho: Authorization: Token <seu_token>."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        tipo = request.user.perfil.tipo
    except Exception:
        return Response(
            {"erro": "Perfil de usuário não encontrado."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if tipo != "gerente":
        return Response(
            {"erro": "Apenas gerentes podem criar, editar ou remover itens do cardápio."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ── Categoria ─────────────────────────────────────────────────────────────────

class CategoriaListView(APIView):
    """
    Lista todas as categorias (público) ou cria uma nova (gerente).

    GET  → público; retorna lista de categorias ordenadas por nome.
    POST → requer token de gerente; cria uma nova categoria; retorna 201.
    """

    @swagger_auto_schema(
        tags=["Cardápio — Categorias"],
        operation_summary="Listar categorias",
        operation_description="Retorna todas as categorias cadastradas. Acesso público, sem autenticação.",
        responses={200: CategoriaSerializer(many=True)},
    )
    def get(self, request):
        """Retorna todas as categorias cadastradas. Acesso público."""
        categorias = Categoria.objects.all()
        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cardápio — Categorias"],
        operation_summary="Criar categoria",
        operation_description="Cria uma nova categoria. Requer token de gerente no cabeçalho Authorization.",
        manual_parameters=[_AUTH_HEADER],
        request_body=CategoriaSerializer,
        responses={
            201: CategoriaSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado — cabeçalho Authorization ausente ou inválido"),
            403: openapi.Response("Acesso negado — apenas gerentes podem criar categorias"),
        },
    )
    def post(self, request):
        """Cria uma nova categoria. Requer autenticação com perfil gerente."""
        erro = _checar_gerente(request)
        if erro:
            return erro
        serializer = CategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoriaDetailView(APIView):
    """
    Recupera (público), atualiza ou remove uma categoria (gerente).

    GET    → público; retorna a categoria com o id informado.
    PUT    → requer token de gerente; substitui todos os campos da categoria.
    DELETE → requer token de gerente; remove a categoria e seus itens em cascata.
    """

    def _get_object(self, pk):
        """Auxiliar: busca a categoria pelo pk ou retorna None."""
        try:
            return Categoria.objects.get(pk=pk)
        except Categoria.DoesNotExist:
            return None

    @swagger_auto_schema(
        tags=["Cardápio — Categorias"],
        operation_summary="Detalhar categoria",
        operation_description="Retorna os dados de uma categoria pelo id. Acesso público.",
        responses={
            200: CategoriaSerializer,
            404: openapi.Response("Categoria não encontrada"),
        },
    )
    def get(self, request, pk):
        """Retorna os dados de uma categoria pelo id. Acesso público."""
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategoriaSerializer(categoria)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cardápio — Categorias"],
        operation_summary="Atualizar categoria",
        operation_description="Substitui todos os campos de uma categoria. Requer token de gerente.",
        manual_parameters=[_AUTH_HEADER],
        request_body=CategoriaSerializer,
        responses={
            200: CategoriaSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Categoria não encontrada"),
        },
    )
    def put(self, request, pk):
        """Atualiza todos os campos de uma categoria. Requer autenticação com perfil gerente."""
        erro = _checar_gerente(request)
        if erro:
            return erro
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategoriaSerializer(categoria, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["Cardápio — Categorias"],
        operation_summary="Remover categoria",
        operation_description="Remove uma categoria pelo id. Requer token de gerente.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            204: openapi.Response("Categoria removida com sucesso"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Categoria não encontrada"),
        },
    )
    def delete(self, request, pk):
        """Remove uma categoria pelo id. Requer autenticação com perfil gerente."""
        erro = _checar_gerente(request)
        if erro:
            return erro
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        categoria.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── ItemCardapio ──────────────────────────────────────────────────────────────

class ItemCardapioListView(APIView):
    """
    Lista todos os itens do cardápio (público) ou cria um novo (gerente).

    GET  → público; aceita query param ?categoria=<id> para filtrar por categoria.
    POST → requer token de gerente; aceita multipart/form-data para upload de imagem; retorna 201.
    """

    @swagger_auto_schema(
        tags=["Cardápio — Itens"],
        operation_summary="Listar itens do cardápio",
        operation_description=(
            "Retorna todos os itens do cardápio. Acesso público.\n\n"
            "Use o parâmetro opcional `?categoria=<id>` para filtrar por categoria.\n\n"
            "O campo `imagem` retorna a URL absoluta da foto do item, ou `null` se não houver imagem."
        ),
        manual_parameters=[
            openapi.Parameter(
                "categoria",
                openapi.IN_QUERY,
                description="Filtra itens pelo id da categoria",
                type=openapi.TYPE_INTEGER,
                required=False,
            )
        ],
        responses={200: ItemCardapioSerializer(many=True)},
    )
    def get(self, request):
        """
        Retorna todos os itens do cardápio. Acesso público.
        Aceita o parâmetro opcional ?categoria=<id> para filtrar por categoria.
        O campo imagem retorna URL absoluta (ex: http://localhost:8000/media/cardapio/foto.jpg).
        """
        itens = ItemCardapio.objects.all()
        categoria_id = request.query_params.get("categoria")
        if categoria_id:
            itens = itens.filter(categoria_id=categoria_id)
        # context={'request': request} garante URL absoluta no campo imagem
        serializer = ItemCardapioSerializer(itens, many=True, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cardápio — Itens"],
        operation_summary="Criar item do cardápio",
        operation_description=(
            "Cria um novo item no cardápio. Requer token de gerente.\n\n"
            "Envie os dados como **multipart/form-data** para incluir uma imagem. "
            "O campo `imagem` é opcional — omita-o para criar o item sem foto."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=_ITEM_FORM_SCHEMA,
        consumes=["multipart/form-data"],
        responses={
            201: ItemCardapioSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
        },
    )
    def post(self, request):
        """
        Cria um novo item do cardápio. Requer autenticação com perfil gerente.
        Aceita multipart/form-data para que o campo imagem (foto do item) possa ser enviado.
        """
        erro = _checar_gerente(request)
        if erro:
            return erro
        serializer = ItemCardapioSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemCardapioDetailView(APIView):
    """
    Recupera (público), atualiza ou remove um item do cardápio (gerente).

    GET    → público; retorna o item com o id informado (campo imagem com URL absoluta).
    PUT    → requer token de gerente; aceita multipart/form-data; se imagem não for enviada,
             a imagem existente é mantida.
    DELETE → requer token de gerente; remove o item do cardápio.
    """

    def _get_object(self, pk):
        """Auxiliar: busca o item pelo pk ou retorna None."""
        try:
            return ItemCardapio.objects.get(pk=pk)
        except ItemCardapio.DoesNotExist:
            return None

    @swagger_auto_schema(
        tags=["Cardápio — Itens"],
        operation_summary="Detalhar item do cardápio",
        operation_description=(
            "Retorna os dados de um item do cardápio pelo id. Acesso público.\n\n"
            "O campo `imagem` retorna a URL absoluta da foto, ou `null` se não houver imagem."
        ),
        responses={
            200: ItemCardapioSerializer,
            404: openapi.Response("Item não encontrado"),
        },
    )
    def get(self, request, pk):
        """Retorna os dados de um item do cardápio pelo id. Acesso público."""
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemCardapioSerializer(item, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Cardápio — Itens"],
        operation_summary="Atualizar item do cardápio",
        operation_description=(
            "Substitui todos os campos de um item do cardápio. Requer token de gerente.\n\n"
            "Envie os dados como **multipart/form-data**. "
            "Se o campo `imagem` não for incluído, a imagem existente é preservada."
        ),
        manual_parameters=[_AUTH_HEADER],
        request_body=_ITEM_FORM_SCHEMA,
        consumes=["multipart/form-data"],
        responses={
            200: ItemCardapioSerializer,
            400: openapi.Response("Dados inválidos"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Item não encontrado"),
        },
    )
    def put(self, request, pk):
        """
        Atualiza todos os campos de um item do cardápio. Requer autenticação com perfil gerente.
        Aceita multipart/form-data. Se nenhuma imagem nova for enviada, a existente é mantida.
        """
        erro = _checar_gerente(request)
        if erro:
            return erro
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemCardapioSerializer(item, data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["Cardápio — Itens"],
        operation_summary="Remover item do cardápio",
        operation_description="Remove um item do cardápio pelo id. Requer token de gerente.",
        manual_parameters=[_AUTH_HEADER],
        responses={
            204: openapi.Response("Item removido com sucesso"),
            401: openapi.Response("Não autenticado"),
            403: openapi.Response("Acesso negado — apenas gerentes"),
            404: openapi.Response("Item não encontrado"),
        },
    )
    def delete(self, request, pk):
        """Remove um item do cardápio pelo id. Requer autenticação com perfil gerente."""
        erro = _checar_gerente(request)
        if erro:
            return erro
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
