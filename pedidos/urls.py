"""URLs do app pedidos."""

from django.urls import path

from .views import PedidoDetailView, PedidoListView

urlpatterns = [
    path("", PedidoListView.as_view(), name="pedido-list"),
    path("<int:pk>/", PedidoDetailView.as_view(), name="pedido-detail"),
]
