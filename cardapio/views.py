"""
views.py — Views de CRUD do cardápio (Categoria e ItemCardapio).

Padrão adotado (conforme slides da disciplina):
  - CategoriaListView    → GET /categorias/        (listar)   POST /categorias/      (criar)
  - CategoriaDetailView  → GET /categorias/<id>/   (detalhe)  PUT /categorias/<id>/  (atualizar)  DELETE /categorias/<id>/ (apagar)
  - ItemCardapioListView   → GET /itens/            (listar)   POST /itens/           (criar)
  - ItemCardapioDetailView → GET /itens/<id>/       (detalhe)  PUT /itens/<id>/       (atualizar)  DELETE /itens/<id>/      (apagar)

Todas as views herdam de APIView e retornam Response com status HTTP explícito.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Categoria, ItemCardapio
from .serializers import CategoriaSerializer, ItemCardapioSerializer


# ── Categoria ─────────────────────────────────────────────────────────────────

class CategoriaListView(APIView):
    """
    Lista todas as categorias ou cria uma nova.

    GET  → retorna lista de categorias ordenadas por nome.
    POST → cria uma nova categoria; retorna 201 em caso de sucesso.
    """

    def get(self, request):
        """Retorna todas as categorias cadastradas."""
        categorias = Categoria.objects.all()
        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Cria uma nova categoria com os dados enviados no corpo da requisição."""
        serializer = CategoriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoriaDetailView(APIView):
    """
    Recupera, atualiza ou remove uma categoria específica pelo id.

    GET    → retorna a categoria com o id informado.
    PUT    → substitui todos os campos da categoria.
    DELETE → remove a categoria (e em cascata seus itens do cardápio).
    """

    def _get_object(self, pk):
        """Auxiliar: busca a categoria ou retorna None."""
        try:
            return Categoria.objects.get(pk=pk)
        except Categoria.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retorna os dados de uma categoria pelo id."""
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategoriaSerializer(categoria)
        return Response(serializer.data)

    def put(self, request, pk):
        """Atualiza todos os campos de uma categoria pelo id."""
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategoriaSerializer(categoria, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Remove uma categoria pelo id."""
        categoria = self._get_object(pk)
        if categoria is None:
            return Response({"erro": "Categoria não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        categoria.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── ItemCardapio ──────────────────────────────────────────────────────────────

class ItemCardapioListView(APIView):
    """
    Lista todos os itens do cardápio ou cria um novo.

    GET  → retorna lista de itens; aceita query param ?categoria=<id> para filtrar.
    POST → cria um novo item; retorna 201 em caso de sucesso.
    """

    def get(self, request):
        """
        Retorna todos os itens do cardápio.
        Aceita o parâmetro opcional ?categoria=<id> para filtrar por categoria.
        """
        itens = ItemCardapio.objects.all()
        categoria_id = request.query_params.get("categoria")
        if categoria_id:
            itens = itens.filter(categoria_id=categoria_id)
        serializer = ItemCardapioSerializer(itens, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Cria um novo item do cardápio com os dados enviados no corpo da requisição."""
        serializer = ItemCardapioSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemCardapioDetailView(APIView):
    """
    Recupera, atualiza ou remove um item do cardápio específico pelo id.

    GET    → retorna o item com o id informado.
    PUT    → substitui todos os campos do item.
    DELETE → remove o item do cardápio.
    """

    def _get_object(self, pk):
        """Auxiliar: busca o item ou retorna None."""
        try:
            return ItemCardapio.objects.get(pk=pk)
        except ItemCardapio.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retorna os dados de um item do cardápio pelo id."""
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemCardapioSerializer(item)
        return Response(serializer.data)

    def put(self, request, pk):
        """Atualiza todos os campos de um item do cardápio pelo id."""
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemCardapioSerializer(item, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Remove um item do cardápio pelo id."""
        item = self._get_object(pk)
        if item is None:
            return Response({"erro": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
