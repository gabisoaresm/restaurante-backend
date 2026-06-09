"""URLs do app accounts — registro, login, logout e troca de senha."""

from django.urls import path

from .views import CustomAuthToken, RegistroView, TrocaSenhaView

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("token-auth/", CustomAuthToken.as_view(), name="token-auth"),
    path("troca-senha/", TrocaSenhaView.as_view(), name="troca-senha"),
]
