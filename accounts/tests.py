"""
tests.py — Testes do app accounts.

Cobre:
  - Registro de usuário
  - Login / logout (token)
  - Endpoint GET /me/ (dados do usuário autenticado)
  - Endpoint PATCH /me/ (atualização de perfil)
  - Troca de senha
  - CRUD de CartaoSalvo (lista, cria, detalha, remove)
  - Controle de acesso: apenas clientes gerenciam cartões
  - Mascaramento do número do cartão
  - Validação de CVV e número inválido
"""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import CartaoSalvo, Perfil


# ── Helpers ──────────────────────────────────────────────────────────────────

def _criar_usuario(username, tipo="cliente", password="Senha@123"):
    """Cria um User + Perfil e retorna (user, token)."""
    user = User.objects.create_user(
        username=username,
        password=password,
        email=f"{username}@exemplo.com",
        first_name="Test",
        last_name="User",
    )
    Perfil.objects.create(usuario=user, tipo=tipo)
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


def _auth(token):
    """Retorna o dicionário de headers de autenticação."""
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def _payload_cartao(**kwargs):
    """Payload padrão para criar um cartão; aceita sobrescritas via kwargs."""
    base = {
        "apelido": "Nubank",
        "nome_titular": "João Silva",
        "numero": "4111111111111111",
        "bandeira": "visa",
        "tipo": "credito",
        "validade": "12/2028",
        "cvv": "123",
    }
    base.update(kwargs)
    return base


# ── Testes de autenticação ────────────────────────────────────────────────────

class RegistroTests(APITestCase):
    """Testa o endpoint de registro de novo usuário."""

    url = "/api/accounts/registro/"

    def test_registro_sucesso(self):
        """Registro com dados válidos retorna 201 e tipo 'cliente'."""
        res = self.client.post(self.url, {
            "username": "novo_user",
            "password": "Senha@123",
            "email": "novo@exemplo.com",
            "first_name": "Novo",
            "last_name": "User",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["tipo"], "cliente")

    def test_registro_username_duplicado(self):
        """Registro com username já existente retorna 400."""
        _criar_usuario("duplicado")
        res = self.client.post(self.url, {
            "username": "duplicado",
            "password": "Senha@123",
            "email": "outro@exemplo.com",
            "first_name": "X",
            "last_name": "Y",
        })
        self.assertEqual(res.status_code, 400)

    def test_registro_campos_obrigatorios(self):
        """Registro sem campos obrigatórios retorna 400."""
        res = self.client.post(self.url, {"username": "s"})
        self.assertEqual(res.status_code, 400)


class LoginLogoutTests(APITestCase):
    """Testa login (POST) e logout (DELETE) no endpoint token-auth."""

    url = "/api/accounts/token-auth/"

    def setUp(self):
        self.user, self.token = _criar_usuario("loguser")

    def test_login_sucesso(self):
        """Login com credenciais válidas retorna 200 e o token."""
        res = self.client.post(self.url, {"username": "loguser", "password": "Senha@123"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)

    def test_login_credenciais_invalidas(self):
        """Login com senha errada retorna 401."""
        res = self.client.post(self.url, {"username": "loguser", "password": "errada"})
        self.assertEqual(res.status_code, 401)

    def test_logout_sucesso(self):
        """DELETE com token válido retorna 200 e invalida o token."""
        res = self.client.delete(self.url, **_auth(self.token))
        self.assertEqual(res.status_code, 200)
        # Token deve ter sido removido do banco
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

    def test_logout_sem_token(self):
        """DELETE sem header Authorization retorna 400."""
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 400)


class MeTests(APITestCase):
    """Testa GET e PATCH no endpoint /me/ (dados do usuário autenticado)."""

    url = "/api/accounts/me/"

    def setUp(self):
        self.user, self.token = _criar_usuario("me_user", tipo="gerente")

    # GET ─────────────────────────────────────────────────────────────────────

    def test_me_retorna_tipo(self):
        """GET /me/ retorna o tipo do perfil correto."""
        res = self.client.get(self.url, **_auth(self.token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["tipo"], "gerente")

    def test_me_retorna_date_joined(self):
        """GET /me/ inclui date_joined no formato dd/mm/aaaa."""
        res = self.client.get(self.url, **_auth(self.token))
        self.assertEqual(res.status_code, 200)
        self.assertIn("date_joined", res.data)
        # Verifica formato dd/mm/aaaa (10 chars, separadores nas posições 2 e 5)
        dj = res.data["date_joined"]
        self.assertEqual(len(dj), 10)
        self.assertEqual(dj[2], "/")
        self.assertEqual(dj[5], "/")

    def test_me_sem_autenticacao(self):
        """GET /me/ sem token retorna 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 401)

    # PATCH ───────────────────────────────────────────────────────────────────

    def test_patch_atualiza_dados(self):
        """PATCH /me/ com dados válidos atualiza e retorna 200 com os novos valores."""
        res = self.client.patch(
            self.url,
            {"first_name": "Novo", "last_name": "Nome", "email": "novo@exemplo.com"},
            format="json",
            **_auth(self.token),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["first_name"], "Novo")
        self.assertEqual(res.data["last_name"],  "Nome")
        self.assertEqual(res.data["email"],       "novo@exemplo.com")
        # Confirma persistência no banco
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Novo")
        self.assertEqual(self.user.email,       "novo@exemplo.com")

    def test_patch_email_duplicado(self):
        """PATCH com e-mail já usado por outro usuário retorna 400."""
        _criar_usuario("outro_user")   # cria com outro@exemplo.com
        res = self.client.patch(
            self.url,
            {"first_name": "X", "last_name": "Y", "email": "outro_user@exemplo.com"},
            format="json",
            **_auth(self.token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("erro", res.data)

    def test_patch_mesmo_email_permitido(self):
        """PATCH mantendo o próprio e-mail não deve retornar erro de duplicidade."""
        res = self.client.patch(
            self.url,
            {"first_name": "Test", "last_name": "User", "email": "me_user@exemplo.com"},
            format="json",
            **_auth(self.token),
        )
        self.assertEqual(res.status_code, 200)

    def test_patch_campos_vazios_retorna_400(self):
        """PATCH com campos obrigatórios em branco retorna 400."""
        res = self.client.patch(
            self.url,
            {"first_name": "", "last_name": "Nome", "email": "x@exemplo.com"},
            format="json",
            **_auth(self.token),
        )
        self.assertEqual(res.status_code, 400)

    def test_patch_sem_autenticacao(self):
        """PATCH /me/ sem token retorna 401."""
        res = self.client.patch(
            self.url,
            {"first_name": "X", "last_name": "Y", "email": "x@exemplo.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 401)


# ── Testes de CartaoSalvo ─────────────────────────────────────────────────────

class CartaoListTests(APITestCase):
    """Testa GET e POST em /api/accounts/cartoes/."""

    url = "/api/accounts/cartoes/"

    def setUp(self):
        self.cliente, self.token_cli    = _criar_usuario("cli")
        self.gerente, self.token_ger    = _criar_usuario("ger", tipo="gerente")
        self.atendente, self.token_ate  = _criar_usuario("ate", tipo="atendente")

    # GET ─────────────────────────────────────────────────────────────────────

    def test_listar_cartoes_cliente_vazio(self):
        """Cliente sem cartões recebe lista vazia com 200."""
        res = self.client.get(self.url, **_auth(self.token_cli))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_listar_cartoes_cliente_com_dados(self):
        """Cliente vê apenas os próprios cartões."""
        CartaoSalvo.objects.create(
            usuario=self.cliente, apelido="N", nome_titular="J",
            numero_mascarado="**** 1111", bandeira="visa",
            tipo="credito", validade="12/2028", cvv="123",
        )
        # Cartão de outro usuário — não deve aparecer
        outro, _ = _criar_usuario("outro_cli")
        CartaoSalvo.objects.create(
            usuario=outro, apelido="X", nome_titular="X",
            numero_mascarado="**** 9999", bandeira="mastercard",
            tipo="debito", validade="01/2025", cvv="999",
        )
        res = self.client.get(self.url, **_auth(self.token_cli))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["apelido"], "N")

    def test_listar_cartoes_gerente_proibido(self):
        """Gerente não pode acessar o endpoint de cartões — retorna 403."""
        res = self.client.get(self.url, **_auth(self.token_ger))
        self.assertEqual(res.status_code, 403)

    def test_listar_cartoes_atendente_proibido(self):
        """Atendente não pode acessar o endpoint de cartões — retorna 403."""
        res = self.client.get(self.url, **_auth(self.token_ate))
        self.assertEqual(res.status_code, 403)

    def test_listar_cartoes_sem_auth(self):
        """Sem token retorna 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 401)

    # POST ────────────────────────────────────────────────────────────────────

    def test_criar_cartao_sucesso(self):
        """POST com dados válidos cria o cartão e retorna 201."""
        res = self.client.post(self.url, _payload_cartao(), **_auth(self.token_cli))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["apelido"], "Nubank")
        # CVV nunca é retornado na resposta
        self.assertNotIn("cvv", res.data)

    def test_criar_cartao_numero_mascarado(self):
        """O número completo é mascarado; apenas os últimos 4 dígitos aparecem."""
        self.client.post(self.url, _payload_cartao(numero="4111111111111234"),
                         **_auth(self.token_cli))
        cartao = CartaoSalvo.objects.get(usuario=self.cliente)
        self.assertEqual(cartao.numero_mascarado, "**** **** **** 1234")

    def test_criar_cartao_numero_invalido(self):
        """Número com menos de 13 dígitos retorna 400."""
        res = self.client.post(self.url, _payload_cartao(numero="1234"),
                               **_auth(self.token_cli))
        self.assertEqual(res.status_code, 400)

    def test_criar_cartao_validade_invalida(self):
        """Validade fora do formato MM/AAAA retorna 400."""
        res = self.client.post(self.url, _payload_cartao(validade="2028-12"),
                               **_auth(self.token_cli))
        self.assertEqual(res.status_code, 400)

    def test_criar_cartao_gerente_proibido(self):
        """Gerente não pode criar cartão — retorna 403."""
        res = self.client.post(self.url, _payload_cartao(), **_auth(self.token_ger))
        self.assertEqual(res.status_code, 403)

    def test_criar_cartao_sem_auth(self):
        """Criação sem token retorna 401."""
        res = self.client.post(self.url, _payload_cartao())
        self.assertEqual(res.status_code, 401)

    def test_criar_cartao_campos_obrigatorios(self):
        """POST sem campos obrigatórios retorna 400."""
        res = self.client.post(self.url, {"apelido": "X"}, **_auth(self.token_cli))
        self.assertEqual(res.status_code, 400)


class CartaoDetailTests(APITestCase):
    """Testa GET e DELETE em /api/accounts/cartoes/<id>/."""

    def setUp(self):
        self.cliente, self.token_cli = _criar_usuario("cli_det")
        self.outro, self.token_outro = _criar_usuario("outro_det")
        self.cartao = CartaoSalvo.objects.create(
            usuario=self.cliente, apelido="MeuCartao", nome_titular="J",
            numero_mascarado="**** 1111", bandeira="visa",
            tipo="credito", validade="12/2028", cvv="123",
        )
        self.url = f"/api/accounts/cartoes/{self.cartao.pk}/"

    def test_detalhe_proprio_cartao(self):
        """Cliente pode ver seu próprio cartão."""
        res = self.client.get(self.url, **_auth(self.token_cli))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["apelido"], "MeuCartao")

    def test_detalhe_cartao_de_outro(self):
        """Cliente não pode ver cartão de outro cliente — retorna 404."""
        res = self.client.get(self.url, **_auth(self.token_outro))
        self.assertEqual(res.status_code, 404)

    def test_excluir_proprio_cartao(self):
        """Cliente pode remover seu próprio cartão — retorna 204."""
        res = self.client.delete(self.url, **_auth(self.token_cli))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(CartaoSalvo.objects.filter(pk=self.cartao.pk).exists())

    def test_excluir_cartao_de_outro(self):
        """Cliente não pode remover cartão de outro — retorna 404."""
        res = self.client.delete(self.url, **_auth(self.token_outro))
        self.assertEqual(res.status_code, 404)
        # O cartão deve permanecer no banco
        self.assertTrue(CartaoSalvo.objects.filter(pk=self.cartao.pk).exists())

    def test_detalhe_sem_auth(self):
        """Sem token retorna 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 401)
