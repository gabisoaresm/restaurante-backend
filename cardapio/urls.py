"""URLs do app cardapio."""

from django.urls import path

from .views import CategoriaDetailView, CategoriaListView, ItemCardapioDetailView, ItemCardapioListView

urlpatterns = [
    path("categorias/", CategoriaListView.as_view(), name="categoria-list"),
    path("categorias/<int:pk>/", CategoriaDetailView.as_view(), name="categoria-detail"),
    path("itens/", ItemCardapioListView.as_view(), name="item-list"),
    path("itens/<int:pk>/", ItemCardapioDetailView.as_view(), name="item-detail"),
]
