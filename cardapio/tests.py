"""
tests.py — Testes do app cardapio.

Cobre:
  - GET /categorias/ — listar (público)
  - POST /categorias/ — criar (gerente)
  - GET /categorias/<id>/ — detalhar (público)
  - PUT /categorias/<id>/ — atualizar (gerente)
  - DELETE /categorias/<id>/ — remover (gerente)
  - GET /itens/ — listar (público), filtro ?categoria=
  - POST /itens/ — criar sem e com imagem (gerente), multipart/form-data
  - GET /itens/<id>/ — detalhar (público), campo imagem presente
  - PUT /itens/<id>/ — atualizar; imagem preservada se não enviada; substituída se enviada
  - DELETE /itens/<id>/ — remover (gerente)
  - Controle de acesso em todos os endpoints de escrita: 401 sem token, 403 para não-gerente
"""

import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Perfil

from .models import Categoria, ItemCardapio


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    """Retorna cabeçalho de autenticação para o cliente de teste."""
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def _criar_categoria(nome="Entradas"):
    """Cria e retorna uma Categoria de teste."""
    return Categoria.objects.create(nome=nome)


def _criar_item(categoria=None, nome="Bruschetta", disponivel=True):
    """Cria e retorna um ItemCardapio de teste."""
    if categoria is None:
        categoria = _criar_categoria()
    return ItemCardapio.objects.create(
        nome=nome,
        descricao="Descrição de teste",
        preco="15.90",
        categoria=categoria,
        disponivel=disponivel,
    )


def _imagem_fake(nome="foto.jpg"):
    """Gera um arquivo de imagem JPEG mínimo em memória para testes de upload."""
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(200, 100, 50)).save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(nome, buf.read(), content_type="image/jpeg")


# Diretório temporário isolado para arquivos de mídia durante os testes
MEDIA_ROOT_TESTE = tempfile.mkdtemp()


# ── Categorias — listagem e criação ──────────────────────────────────────────

class CategoriaListTests(APITestCase):
    """Testa GET e POST em /api/cardapio/categorias/."""

    url = "/api/cardapio/categorias/"

    def setUp(self):
        self.gerente,   self.tok_ger = _criar_usuario("cat_ger", tipo="gerente")
        self.cliente,   self.tok_cli = _criar_usuario("cat_cli", tipo="cliente")
        self.atendente, self.tok_ate = _criar_usuario("cat_ate", tipo="atendente")

    # GET — público ─────────────────────────────────────────────────────────────

    def test_listar_categorias_publico(self):
        """GET sem autenticação retorna 200 e lista de categorias."""
        _criar_categoria("Entradas")
        _criar_categoria("Bebidas")
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_listar_categorias_vazio(self):
        """GET com banco vazio retorna 200 e lista vazia."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_resposta_contem_id_e_nome(self):
        """Cada categoria retorna os campos id e nome."""
        _criar_categoria("Sobremesas")
        res = self.client.get(self.url)
        self.assertIn("id",   res.data[0])
        self.assertIn("nome", res.data[0])

    # POST — gerente ─────────────────────────────────────────────────────────

    def test_criar_categoria_gerente(self):
        """Gerente cria categoria com dados válidos — retorna 201."""
        res = self.client.post(self.url, {"nome": "Pratos"}, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["nome"], "Pratos")
        self.assertTrue(Categoria.objects.filter(nome="Pratos").exists())

    def test_criar_categoria_sem_nome_retorna_400(self):
        """POST sem nome retorna 400."""
        res = self.client.post(self.url, {}, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 400)

    def test_criar_categoria_cliente_retorna_403(self):
        """Cliente não pode criar categorias — retorna 403."""
        res = self.client.post(self.url, {"nome": "X"}, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)

    def test_criar_categoria_atendente_retorna_403(self):
        """Atendente não pode criar categorias — retorna 403."""
        res = self.client.post(self.url, {"nome": "X"}, **_auth(self.tok_ate))
        self.assertEqual(res.status_code, 403)

    def test_criar_categoria_sem_auth_retorna_401(self):
        """POST sem token retorna 401."""
        res = self.client.post(self.url, {"nome": "X"})
        self.assertEqual(res.status_code, 401)


# ── Categorias — detalhe, atualização e remoção ───────────────────────────────

class CategoriaDetailTests(APITestCase):
    """Testa GET, PUT e DELETE em /api/cardapio/categorias/<id>/."""

    def setUp(self):
        self.gerente, self.tok_ger = _criar_usuario("catd_ger", tipo="gerente")
        self.cliente, self.tok_cli = _criar_usuario("catd_cli", tipo="cliente")
        self.cat = _criar_categoria("Petiscos")
        self.url = f"/api/cardapio/categorias/{self.cat.pk}/"

    # GET — público ─────────────────────────────────────────────────────────────

    def test_detalhar_categoria_publico(self):
        """GET sem autenticação retorna 200 com os dados da categoria."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nome"], "Petiscos")

    def test_detalhar_categoria_inexistente_retorna_404(self):
        """GET de id inexistente retorna 404."""
        res = self.client.get("/api/cardapio/categorias/99999/")
        self.assertEqual(res.status_code, 404)

    # PUT — gerente ─────────────────────────────────────────────────────────

    def test_atualizar_categoria_gerente(self):
        """Gerente atualiza categoria — retorna 200 e persiste a mudança."""
        res = self.client.put(self.url, {"nome": "Entradas"}, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nome"], "Entradas")
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.nome, "Entradas")

    def test_atualizar_categoria_sem_nome_retorna_400(self):
        """PUT sem nome retorna 400."""
        res = self.client.put(self.url, {}, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 400)

    def test_atualizar_categoria_cliente_retorna_403(self):
        """Cliente não pode atualizar categorias — retorna 403."""
        res = self.client.put(self.url, {"nome": "X"}, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)

    def test_atualizar_categoria_sem_auth_retorna_401(self):
        """PUT sem token retorna 401."""
        res = self.client.put(self.url, {"nome": "X"})
        self.assertEqual(res.status_code, 401)

    # DELETE — gerente ─────────────────────────────────────────────────────

    def test_remover_categoria_gerente(self):
        """Gerente remove categoria — retorna 204 e remove do banco."""
        res = self.client.delete(self.url, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Categoria.objects.filter(pk=self.cat.pk).exists())

    def test_remover_categoria_cliente_retorna_403(self):
        """Cliente não pode remover categorias — retorna 403."""
        res = self.client.delete(self.url, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Categoria.objects.filter(pk=self.cat.pk).exists())

    def test_remover_categoria_sem_auth_retorna_401(self):
        """DELETE sem token retorna 401."""
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 401)

    def test_remover_categoria_inexistente_retorna_404(self):
        """DELETE de id inexistente retorna 404."""
        res = self.client.delete("/api/cardapio/categorias/99999/", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 404)


# ── Itens — listagem e criação ────────────────────────────────────────────────

@override_settings(MEDIA_ROOT=MEDIA_ROOT_TESTE)
class ItemListTests(APITestCase):
    """Testa GET e POST em /api/cardapio/itens/."""

    url = "/api/cardapio/itens/"

    @classmethod
    def tearDownClass(cls):
        """Remove o diretório temporário de mídia ao fim da suíte."""
        shutil.rmtree(MEDIA_ROOT_TESTE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.gerente, self.tok_ger = _criar_usuario("item_ger", tipo="gerente")
        self.cliente, self.tok_cli = _criar_usuario("item_cli", tipo="cliente")
        self.cat = _criar_categoria("Pratos")

    # GET — público ─────────────────────────────────────────────────────────────

    def test_listar_itens_publico(self):
        """GET sem autenticação retorna 200 e lista todos os itens."""
        _criar_item(self.cat, "Lasanha")
        _criar_item(self.cat, "Risoto")
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_listar_itens_vazio(self):
        """GET com banco vazio retorna 200 e lista vazia."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_filtro_por_categoria(self):
        """?categoria=<id> retorna apenas os itens da categoria indicada."""
        outra_cat = _criar_categoria("Bebidas")
        _criar_item(self.cat,   "Lasanha")
        _criar_item(outra_cat,  "Suco")
        res = self.client.get(f"{self.url}?categoria={self.cat.pk}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["nome"], "Lasanha")

    def test_resposta_contem_campo_imagem(self):
        """Resposta do GET inclui o campo imagem (null quando não há foto)."""
        _criar_item(self.cat)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("imagem", res.data[0])
        self.assertIsNone(res.data[0]["imagem"])

    def test_resposta_contem_todos_os_campos(self):
        """Cada item retorna os campos esperados pelo frontend."""
        _criar_item(self.cat)
        res = self.client.get(self.url)
        campos = {"id", "nome", "descricao", "preco", "categoria", "categoria_nome", "disponivel", "imagem"}
        self.assertTrue(campos.issubset(res.data[0].keys()))

    # POST sem imagem — gerente ────────────────────────────────────────────────

    def test_criar_item_sem_imagem(self):
        """Gerente cria item sem foto — retorna 201 e imagem é null."""
        dados = {
            "nome": "Caprese",
            "descricao": "Tomate e mussarela",
            "preco": "22.00",
            "categoria": self.cat.pk,
            "disponivel": "true",
        }
        res = self.client.post(self.url, dados, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["nome"], "Caprese")
        self.assertIsNone(res.data["imagem"])

    # POST com imagem — gerente ────────────────────────────────────────────────

    def test_criar_item_com_imagem(self):
        """Gerente cria item com foto — retorna 201 e imagem aponta para URL."""
        dados = {
            "nome": "Bruschetta",
            "descricao": "Pão tostado com tomate",
            "preco": "18.50",
            "categoria": self.cat.pk,
            "disponivel": "true",
            "imagem": _imagem_fake(),
        }
        res = self.client.post(self.url, dados, format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(res.data["imagem"])
        # Confirma que o arquivo foi salvo no banco
        item = ItemCardapio.objects.get(nome="Bruschetta")
        self.assertTrue(bool(item.imagem))

    def test_criar_item_campo_imagem_url_absoluta(self):
        """A URL da imagem retornada é absoluta (começa com http)."""
        dados = {
            "nome": "Tiramisu",
            "descricao": "Sobremesa italiana",
            "preco": "19.00",
            "categoria": self.cat.pk,
            "disponivel": "true",
            "imagem": _imagem_fake("tiramisu.jpg"),
        }
        res = self.client.post(self.url, dados, format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["imagem"].startswith("http"))

    # POST — controle de acesso ─────────────────────────────────────────────────

    def test_criar_item_cliente_retorna_403(self):
        """Cliente não pode criar itens — retorna 403."""
        dados = {"nome": "X", "descricao": "Y", "preco": "1.00", "categoria": self.cat.pk}
        res = self.client.post(self.url, dados, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)

    def test_criar_item_sem_auth_retorna_401(self):
        """POST sem token retorna 401."""
        dados = {"nome": "X", "descricao": "Y", "preco": "1.00", "categoria": self.cat.pk}
        res = self.client.post(self.url, dados)
        self.assertEqual(res.status_code, 401)

    def test_criar_item_campos_obrigatorios_retorna_400(self):
        """POST sem campos obrigatórios retorna 400."""
        res = self.client.post(self.url, {"nome": "Incompleto"}, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 400)


# ── Itens — detalhe, atualização e remoção ────────────────────────────────────

@override_settings(MEDIA_ROOT=MEDIA_ROOT_TESTE)
class ItemDetailTests(APITestCase):
    """Testa GET, PUT e DELETE em /api/cardapio/itens/<id>/."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT_TESTE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.gerente, self.tok_ger = _criar_usuario("itd_ger", tipo="gerente")
        self.cliente, self.tok_cli = _criar_usuario("itd_cli", tipo="cliente")
        self.cat  = _criar_categoria("Massas")
        self.item = _criar_item(self.cat, "Penne")
        self.url  = f"/api/cardapio/itens/{self.item.pk}/"

    def _payload_completo(self, **extra):
        """Payload mínimo válido para PUT."""
        base = {
            "nome":       "Penne Atualizado",
            "descricao":  "Massa curta com molho",
            "preco":      "27.00",
            "categoria":  self.cat.pk,
            "disponivel": "true",
        }
        base.update(extra)
        return base

    # GET — público ─────────────────────────────────────────────────────────────

    def test_detalhar_item_publico(self):
        """GET sem autenticação retorna 200 com os dados do item."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nome"], "Penne")

    def test_detalhar_item_inclui_imagem_nula(self):
        """Item sem foto retorna imagem=null no GET."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("imagem", res.data)
        self.assertIsNone(res.data["imagem"])

    def test_detalhar_item_inexistente_retorna_404(self):
        """GET de id inexistente retorna 404."""
        res = self.client.get("/api/cardapio/itens/99999/")
        self.assertEqual(res.status_code, 404)

    # PUT sem nova imagem — imagem existente deve ser preservada ───────────────

    def test_put_sem_imagem_preserva_foto_existente(self):
        """PUT sem campo imagem mantém a foto atual do item inalterada."""
        # Salva uma imagem no item diretamente
        self.item.imagem.save("original.jpg", _imagem_fake("original.jpg"), save=True)
        caminho_original = self.item.imagem.name

        # PUT sem enviar imagem nova
        res = self.client.put(self.url, self._payload_completo(),
                              format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)

        self.item.refresh_from_db()
        # O caminho do arquivo no banco deve ser o mesmo de antes
        self.assertEqual(self.item.imagem.name, caminho_original)

    def test_put_com_imagem_nova_substitui_foto(self):
        """PUT com nova imagem atualiza o campo e retorna URL não-nula."""
        res = self.client.put(
            self.url,
            self._payload_completo(imagem=_imagem_fake("nova.jpg")),
            format="multipart",
            **_auth(self.tok_ger),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["imagem"])
        self.item.refresh_from_db()
        self.assertTrue(bool(self.item.imagem))

    def test_put_item_sem_imagem_inicialmente(self):
        """PUT em item sem foto e sem enviar imagem — imagem continua null."""
        res = self.client.put(self.url, self._payload_completo(),
                              format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["imagem"])

    def test_put_atualiza_campos_texto(self):
        """PUT atualiza nome, descrição e preço corretamente."""
        res = self.client.put(self.url, self._payload_completo(),
                              format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nome"], "Penne Atualizado")
        self.item.refresh_from_db()
        self.assertEqual(self.item.nome, "Penne Atualizado")

    def test_put_campos_obrigatorios_retorna_400(self):
        """PUT sem campos obrigatórios retorna 400."""
        res = self.client.put(self.url, {"nome": "Só nome"},
                              format="multipart", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 400)

    # PUT — controle de acesso ─────────────────────────────────────────────────

    def test_put_cliente_retorna_403(self):
        """Cliente não pode atualizar itens — retorna 403."""
        res = self.client.put(self.url, self._payload_completo(),
                              format="multipart", **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)

    def test_put_sem_auth_retorna_401(self):
        """PUT sem token retorna 401."""
        res = self.client.put(self.url, self._payload_completo(), format="multipart")
        self.assertEqual(res.status_code, 401)

    def test_put_item_inexistente_retorna_404(self):
        """PUT em id inexistente retorna 404."""
        res = self.client.put(
            "/api/cardapio/itens/99999/",
            self._payload_completo(),
            format="multipart",
            **_auth(self.tok_ger),
        )
        self.assertEqual(res.status_code, 404)

    # DELETE — gerente ─────────────────────────────────────────────────────────

    def test_remover_item_gerente(self):
        """Gerente remove item — retorna 204 e remove do banco."""
        res = self.client.delete(self.url, **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(ItemCardapio.objects.filter(pk=self.item.pk).exists())

    def test_remover_item_cliente_retorna_403(self):
        """Cliente não pode remover itens — retorna 403."""
        res = self.client.delete(self.url, **_auth(self.tok_cli))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(ItemCardapio.objects.filter(pk=self.item.pk).exists())

    def test_remover_item_sem_auth_retorna_401(self):
        """DELETE sem token retorna 401."""
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 401)

    def test_remover_item_inexistente_retorna_404(self):
        """DELETE de id inexistente retorna 404."""
        res = self.client.delete("/api/cardapio/itens/99999/", **_auth(self.tok_ger))
        self.assertEqual(res.status_code, 404)
