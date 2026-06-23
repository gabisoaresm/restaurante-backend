"""URLs do app accounts — registro, login, logout, troca de senha, usuário atual, cartões e gerenciamento de usuários."""

from django.urls import path

from .views import (
    CartaoDetailView,
    CartaoListView,
    CustomAuthToken,
    RegistroView,
    TrocaSenhaView,
    UsuarioAtualView,
    UsuarioAlterarPerfilView,
    UsuariosListView,
)

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("token-auth/", CustomAuthToken.as_view(), name="token-auth"),
    path("troca-senha/", TrocaSenhaView.as_view(), name="troca-senha"),
    path("me/", UsuarioAtualView.as_view(), name="usuario-atual"),
    path("cartoes/", CartaoListView.as_view(), name="cartao-list"),
    path("cartoes/<int:pk>/", CartaoDetailView.as_view(), name="cartao-detail"),
    path("usuarios/", UsuariosListView.as_view(), name="usuarios-list"),
    path("usuarios/<int:pk>/", UsuarioAlterarPerfilView.as_view(), name="usuario-alterar-perfil"),
]
