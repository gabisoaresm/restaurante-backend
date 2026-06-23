"""URLs do app accounts — registro, login, logout, troca de senha, usuário atual e cartões."""

from django.urls import path

from .views import CartaoDetailView, CartaoListView, CustomAuthToken, RegistroView, TrocaSenhaView, UsuarioAtualView

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("token-auth/", CustomAuthToken.as_view(), name="token-auth"),
    path("troca-senha/", TrocaSenhaView.as_view(), name="troca-senha"),
    path("me/", UsuarioAtualView.as_view(), name="usuario-atual"),
    path("cartoes/", CartaoListView.as_view(), name="cartao-list"),
    path("cartoes/<int:pk>/", CartaoDetailView.as_view(), name="cartao-detail"),
]
