"""
tests.py — Testes do app pedidos.

Cobre:
  - Criar pedido com cartão válido + CVV correto → 201
  - Falha com CVV errado → 400
  - Falha com cartão de outro cliente → 400
  - Falha com cartão inexistente → 400
  - forma_pagamento derivada automaticamente do tipo do cartão
  - Regressão: listar pedidos por perfil (cliente / atendente / gerente)
  - Regressão: avanço de status pelo atendente
  - Regressão: exclusão de pedido pelo gerente
  - Regressão: cliente não pode ver pedido de outro cliente
"""

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import CartaoSalvo, Perfil
from cardapio.models import Categoria, ItemCardapio
from .models import Pedido


# ── Helpers ──────────────────────────────────────────────────────────────────

def _criar_usuario(username, tipo="cliente", password="Senha@123"):
    """Cria User + Perfil e retorna (user, token)."""
    user = User.objects.create_user(
        username=username, password=password,
        email=f"{username}@ex.com", first_name="T", last_name="U",
    )
    Perfil.objects.create(usuario=user, tipo=tipo)
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


def _auth(token):
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def _criar_item():
    """Cria e retorna um ItemCardapio básico."""
    cat, _ = Categoria.objects.get_or_create(nome="Pratos")
    return ItemCardapio.objects.create(
        nome="Frango", descricao="Grelhado", preco="29.90",
        categoria=cat, disponivel=True,
    )


def _criar_cartao(usuario, tipo="credito", cvv="123"):
    """Cria e retorna um CartaoSalvo para o usuário dado."""
    return CartaoSalvo.objects.create(
        usuario=usuario, apelido="Teste", nome_titular="Test User",
        numero_mascarado="**** **** **** 1111",
        bandeira="visa", tipo=tipo,
        validade="12/2028", cvv=cvv,
    )


def _payload_pedido(cartao_id, cvv="123", observacoes="", item_id=None, quantidade=1):
    """Monta payload de criação de pedido."""
    itens = [{"item": item_id, "quantidade": quantidade}] if item_id else []
    return {
        "cartao_id": cartao_id,
        "cvv": cvv,
        "observacoes": observacoes,
        "itens": itens,
    }


# ── Testes de criação de pedido ───────────────────────────────────────────────

class CriarPedidoTests(APITestCase):
    """Testa POST /api/pedidos/ com fluxo de pagamento por cartão."""

    url = "/api/pedidos/"

    def setUp(self):
        self.cliente, self.token = _criar_usuario("pedcli")
        self.item = _criar_item()
        self.cartao_cred = _criar_cartao(self.cliente, tipo="credito", cvv="111")
        self.cartao_deb  = _criar_cartao(self.cliente, tipo="debito",  cvv="222")

    def test_criar_pedido_cartao_credito(self):
        """Pedido com cartão de crédito é criado com forma_pagamento=cartao_credito."""
        payload = _payload_pedido(self.cartao_cred.pk, cvv="111", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["forma_pagamento"], "cartao_credito")
        self.assertEqual(res.data["status"], "recebido")

    def test_criar_pedido_cartao_debito(self):
        """Pedido com cartão de débito é criado com forma_pagamento=cartao_debito."""
        payload = _payload_pedido(self.cartao_deb.pk, cvv="222", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["forma_pagamento"], "cartao_debito")

    def test_criar_pedido_cvv_errado(self):
        """CVV incorreto retorna 400."""
        payload = _payload_pedido(self.cartao_cred.pk, cvv="999", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 400)
        self.assertIn("cvv", str(res.data).lower())

    def test_criar_pedido_cartao_de_outro_cliente(self):
        """Usar cartão de outro cliente retorna 400."""
        outro, _ = _criar_usuario("outro_cli_ped")
        cartao_outro = _criar_cartao(outro, cvv="456")
        payload = _payload_pedido(cartao_outro.pk, cvv="456", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 400)

    def test_criar_pedido_cartao_inexistente(self):
        """cartao_id inválido retorna 400."""
        payload = _payload_pedido(99999, cvv="111", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 400)

    def test_criar_pedido_gerente_proibido(self):
        """Gerente não pode criar pedidos — retorna 403."""
        _, token_ger = _criar_usuario("gerped", tipo="gerente")
        cartao = _criar_cartao(User.objects.get(username="gerped"), cvv="333")
        payload = _payload_pedido(cartao.pk, cvv="333", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json", **_auth(token_ger))
        self.assertEqual(res.status_code, 403)

    def test_criar_pedido_sem_auth(self):
        """Sem token retorna 401."""
        payload = _payload_pedido(self.cartao_cred.pk, cvv="111", item_id=self.item.pk)
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, 401)

    def test_criar_pedido_sem_itens(self):
        """Pedido sem itens retorna 400."""
        payload = {"cartao_id": self.cartao_cred.pk, "cvv": "111", "itens": []}
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 400)

    def test_pedido_com_observacoes(self):
        """Observações são gravadas corretamente."""
        payload = _payload_pedido(
            self.cartao_cred.pk, cvv="111",
            observacoes="Sem cebola", item_id=self.item.pk,
        )
        res = self.client.post(self.url, payload, format="json", **_auth(self.token))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["observacoes"], "Sem cebola")


# ── Testes de listagem e detalhe de pedidos ───────────────────────────────────

class ListarPedidosTests(APITestCase):
    """Testa GET /api/pedidos/ com visibilidade por perfil."""

    url = "/api/pedidos/"

    def setUp(self):
        self.cli_a, self.tok_a = _criar_usuario("cli_a")
        self.cli_b, self.tok_b = _criar_usuario("cli_b")
        self.ate,   self.tok_at = _criar_usuario("ate_list", tipo="atendente")
        self.ger,   self.tok_ger = _criar_usuario("ger_list", tipo="gerente")
        item = _criar_item()
        cartao_a = _criar_cartao(self.cli_a, cvv="111")
        cartao_b = _criar_cartao(self.cli_b, cvv="222")
        # Cria um pedido para cada cliente diretamente no banco
        Pedido.objects.create(
            cliente=self.cli_a, forma_pagamento="cartao_credito",
            cartao_utilizado=cartao_a,
        )
        Pedido.objects.create(
            cliente=self.cli_b, forma_pagamento="cartao_debito",
            cartao_utilizado=cartao_b,
        )

    def test_cliente_ve_apenas_proprios_pedidos(self):
        """Cliente A vê apenas 1 pedido (o seu)."""
        res = self.client.get(self.url, **_auth(self.tok_a))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["cliente_username"], "cli_a")

    def test_atendente_ve_todos_os_pedidos(self):
        """Atendente vê todos os pedidos (2)."""
        res = self.client.get(self.url, **_auth(self.tok_at))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_gerente_ve_todos_os_pedidos(self):
        """Gerente vê todos os pedidos (2)."""
        res = self.client.get(self.url, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_sem_auth_retorna_401(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 401)


class DetalhePedidoTests(APITestCase):
    """Testa GET /api/pedidos/<id>/ com controle de acesso."""

    def setUp(self):
        self.cli_a, self.tok_a = _criar_usuario("det_cli_a")
        self.cli_b, self.tok_b = _criar_usuario("det_cli_b")
        self.ate,   self.tok_at = _criar_usuario("det_ate", tipo="atendente")
        cartao = _criar_cartao(self.cli_a, cvv="111")
        self.pedido = Pedido.objects.create(
            cliente=self.cli_a, forma_pagamento="cartao_credito",
            cartao_utilizado=cartao,
        )
        self.url = f"/api/pedidos/{self.pedido.pk}/"

    def test_cliente_ve_proprio_pedido(self):
        res = self.client.get(self.url, **_auth(self.tok_a))
        self.assertEqual(res.status_code, 200)

    def test_cliente_nao_ve_pedido_de_outro(self):
        """Retorna 404 para não revelar existência do pedido de outro cliente."""
        res = self.client.get(self.url, **_auth(self.tok_b))
        self.assertEqual(res.status_code, 404)

    def test_atendente_ve_qualquer_pedido(self):
        res = self.client.get(self.url, **_auth(self.tok_at))
        self.assertEqual(res.status_code, 200)


# ── Testes de avanço de status ────────────────────────────────────────────────

class AvancoStatusTests(APITestCase):
    """Testa PATCH /api/pedidos/<id>/ para avanço de status."""

    def setUp(self):
        self.cli, self.tok_cli = _criar_usuario("sta_cli")
        self.ate, self.tok_at  = _criar_usuario("sta_ate", tipo="atendente")
        self.ger, self.tok_ger = _criar_usuario("sta_ger", tipo="gerente")
        cartao = _criar_cartao(self.cli, cvv="111")
        self.pedido = Pedido.objects.create(
            cliente=self.cli, forma_pagamento="cartao_credito",
            cartao_utilizado=cartao,
        )
        self.url = f"/api/pedidos/{self.pedido.pk}/"

    def test_atendente_avanca_status(self):
        """Atendente avança recebido → em_preparo."""
        res = self.client.patch(self.url, {"status": "em_preparo"}, format="json",
                                **_auth(self.tok_at))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "em_preparo")

    def test_status_invalido_retorna_400(self):
        """Tentar pular status retorna 400."""
        res = self.client.patch(self.url, {"status": "entregue"}, format="json",
                                **_auth(self.tok_at))
        self.assertEqual(res.status_code, 400)

    def test_cliente_nao_pode_atualizar_status(self):
        """Cliente não pode alterar status — retorna 403."""
        res = self.client.patch(self.url, {"status": "em_preparo"}, format="json",
                                **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)

    def test_fluxo_completo_de_status(self):
        """Verifica o fluxo completo: recebido → em_preparo → pronto → entregue."""
        for proximo in ("em_preparo", "pronto", "entregue"):
            res = self.client.patch(self.url, {"status": proximo}, format="json",
                                    **_auth(self.tok_ger))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data["status"], proximo)

    def test_nao_avanca_apos_entregue(self):
        """Pedido entregue não pode ter status alterado — retorna 400."""
        self.pedido.status = "entregue"
        self.pedido.save()
        res = self.client.patch(self.url, {"status": "entregue"}, format="json",
                                **_auth(self.tok_at))
        self.assertEqual(res.status_code, 400)


# ── Testes de exclusão de pedido ──────────────────────────────────────────────

class ExcluirPedidoTests(APITestCase):
    """Testa DELETE /api/pedidos/<id>/."""

    def setUp(self):
        self.cli, self.tok_cli = _criar_usuario("del_cli")
        self.ger, self.tok_ger = _criar_usuario("del_ger", tipo="gerente")
        self.ate, self.tok_at  = _criar_usuario("del_ate", tipo="atendente")
        cartao = _criar_cartao(self.cli, cvv="111")
        self.pedido = Pedido.objects.create(
            cliente=self.cli, forma_pagamento="cartao_credito",
            cartao_utilizado=cartao,
        )
        self.url = f"/api/pedidos/{self.pedido.pk}/"

    def test_gerente_pode_excluir(self):
        res = self.client.delete(self.url, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_atendente_nao_pode_excluir(self):
        res = self.client.delete(self.url, **_auth(self.tok_at))
        self.assertEqual(res.status_code, 403)

    def test_cliente_nao_pode_excluir(self):
        res = self.client.delete(self.url, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)


# ── Testes de filtros ─────────────────────────────────────────────────────────

class FiltroPedidosTests(APITestCase):
    """Testa os query params ?status= e ?data= em GET /api/pedidos/."""

    url = "/api/pedidos/"

    def setUp(self):
        self.ger, self.tok_ger = _criar_usuario("fil_ger", tipo="gerente")
        self.cli, self.tok_cli = _criar_usuario("fil_cli")
        cartao = _criar_cartao(self.cli, cvv="111")
        Pedido.objects.create(
            cliente=self.cli, forma_pagamento="cartao_credito",
            cartao_utilizado=cartao, status="recebido",
        )
        p2 = Pedido.objects.create(
            cliente=self.cli, forma_pagamento="cartao_debito",
            cartao_utilizado=cartao, status="recebido",
        )
        p2.status = "em_preparo"
        p2.save()

    def test_filtro_status_recebido(self):
        res = self.client.get(f"{self.url}?status=recebido", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_filtro_status_em_preparo(self):
        res = self.client.get(f"{self.url}?status=em_preparo", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
