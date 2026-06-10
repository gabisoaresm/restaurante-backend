from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        """Conecta os receptores de sinais quando o app é carregado."""
        import accounts.signals  # noqa: F401
