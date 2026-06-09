"""URLs do app accounts — registro, login e logout."""

from django.urls import path

from .views import CustomAuthToken, RegistroView

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("token-auth/", CustomAuthToken.as_view(), name="token-auth"),
]
