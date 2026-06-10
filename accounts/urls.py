"""URLs do app accounts — registro, login, logout, troca de senha e usuário atual."""

from django.urls import path

from .views import CustomAuthToken, RegistroView, TrocaSenhaView, UsuarioAtualView

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("token-auth/", CustomAuthToken.as_view(), name="token-auth"),
    path("troca-senha/", TrocaSenhaView.as_view(), name="troca-senha"),
    path("me/", UsuarioAtualView.as_view(), name="usuario-atual"),
]
