"""Envio de e-mails via Microsoft Graph API (sem depender do Outlook/COM).

Usa as mesmas credenciais já utilizadas na leitura de e-mails (Cielo e
Bradesco): GRAPH_CLIENT_ID, GRAPH_TENANT_ID, GRAPH_CLIENT_SECRET e
GRAPH_BASE_URL, lidas das Credenciais Genéricas do Windows (com fallback
para variáveis de ambiente / .env).

Requisito no Azure (App Registration): permissão de aplicativo
``Mail.Send`` com consentimento do administrador.

Exemplo de uso:
    from SendEmailGraph import SendEmailGraph

    SendEmailGraph.enviar_email(
        destinatarios=["fulano@partage.com.br"],
        assunto="Início da automação",
        corpo_html="<p>Automação iniciada.</p>",
    )
"""

import base64
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

REMETENTE_PADRAO = "automacao.estacionamento@partage.com.br"
TIMEOUT_SEGUNDOS = 30
TENTATIVAS = 3
LIMITE_ANEXO_BYTES = 3 * 1024 * 1024  # anexo inline do Graph: até ~3 MB


class SendEmailGraphError(Exception):
    """Erro ao enviar e-mail via Microsoft Graph."""


class SendEmailGraph:
    """Envia e-mails pela Graph API usando client credentials."""

    _token: str | None = None
    _token_expira_em: float = 0.0

    # ------------------------------------------------------------------
    # Credenciais
    # ------------------------------------------------------------------
    @staticmethod
    def _ler_credencial(chave: str) -> str | None:
        """Lê a chave nas Credenciais Genéricas do Windows ou no ambiente."""
        valor = os.getenv(chave)
        if valor:
            return valor

        try:
            import pywintypes  # noqa: PLC0415
            import win32cred  # noqa: PLC0415

            cred = win32cred.CredRead(chave, win32cred.CRED_TYPE_GENERIC, 0)
            blob: bytes = cred["CredentialBlob"]
            return blob.decode("utf-16-le")
        except pywintypes.error as exc:
            # 1168 = ERROR_NOT_FOUND (credencial não existe)
            logger.debug("Credencial %s não encontrada: %s", chave, exc)
            return None

    @classmethod
    def _obter_config(cls) -> dict[str, str]:
        config = {
            chave: cls._ler_credencial(chave)
            for chave in (
                "GRAPH_CLIENT_ID",
                "GRAPH_TENANT_ID",
                "GRAPH_CLIENT_SECRET",
                "GRAPH_BASE_URL",
            )
        }
        config["GRAPH_BASE_URL"] = (
            config["GRAPH_BASE_URL"] or "https://graph.microsoft.com/v1.0"
        ).rstrip("/")

        faltando = [k for k, v in config.items() if not v]
        if faltando:
            raise SendEmailGraphError(
                f"Credenciais Graph ausentes: {', '.join(faltando)}"
            )
        return config  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Token
    # ------------------------------------------------------------------
    @classmethod
    def _obter_token(cls) -> str:
        """Obtém (e reaproveita até expirar) o token de acesso."""
        if cls._token and time.time() < cls._token_expira_em - 60:
            return cls._token

        config = cls._obter_config()
        url = (
            f"https://login.microsoftonline.com/"
            f"{config['GRAPH_TENANT_ID']}/oauth2/v2.0/token"
        )
        resposta = requests.post(
            url,
            data={
                "client_id": config["GRAPH_CLIENT_ID"],
                "client_secret": config["GRAPH_CLIENT_SECRET"],
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        if resposta.status_code != 200:
            raise SendEmailGraphError(
                f"Falha ao obter token ({resposta.status_code}): "
                f"{resposta.text}"
            )

        dados = resposta.json()
        cls._token = dados["access_token"]
        cls._token_expira_em = time.time() + int(dados.get("expires_in", 3600))
        return cls._token

    # ------------------------------------------------------------------
    # Montagem da mensagem
    # ------------------------------------------------------------------
    @staticmethod
    def _montar_destinatarios(enderecos: list[str] | None) -> list[dict]:
        return [
            {"emailAddress": {"address": e.strip()}}
            for e in (enderecos or [])
            if e and e.strip()
        ]

    @staticmethod
    def _montar_anexos(anexos: list[str | Path] | None) -> list[dict]:
        resultado: list[dict] = []
        for item in anexos or []:
            caminho = Path(item)
            if not caminho.is_file():
                raise SendEmailGraphError(f"Anexo não encontrado: {caminho}")
            if caminho.stat().st_size > LIMITE_ANEXO_BYTES:
                raise SendEmailGraphError(
                    f"Anexo acima de 3 MB não suportado: {caminho.name}"
                )
            resultado.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": caminho.name,
                    "contentBytes": base64.b64encode(
                        caminho.read_bytes()
                    ).decode("ascii"),
                }
            )
        return resultado

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    @classmethod
    def enviar_email(
        cls,
        destinatarios: list[str] | str,
        assunto: str,
        corpo_html: str,
        cc: list[str] | None = None,
        anexos: list[str | Path] | None = None,
        remetente: str | None = None,
    ) -> None:
        """Envia um e-mail HTML.

        Args:
            destinatarios: lista de e-mails (ou string separada por ';').
            assunto: assunto da mensagem.
            corpo_html: corpo em HTML.
            cc: lista de e-mails em cópia (opcional).
            anexos: caminhos de arquivos a anexar (opcional, até 3 MB cada).
            remetente: caixa que envia; padrão EMAIL_MAIN_USER ou
                ``REMETENTE_PADRAO``.

        Raises:
            SendEmailGraphError: se o envio falhar após as tentativas.
        """
        if isinstance(destinatarios, str):
            destinatarios = [
                e for e in destinatarios.replace(",", ";").split(";") if e
            ]

        para = cls._montar_destinatarios(destinatarios)
        if not para:
            raise SendEmailGraphError("Nenhum destinatário informado.")

        remetente = (
            remetente
            or cls._ler_credencial("EMAIL_MAIN_USER")
            or REMETENTE_PADRAO
        )

        mensagem: dict = {
            "subject": assunto,
            "body": {"contentType": "HTML", "content": corpo_html},
            "toRecipients": para,
            "ccRecipients": cls._montar_destinatarios(cc),
        }
        anexos_graph = cls._montar_anexos(anexos)
        if anexos_graph:
            mensagem["attachments"] = anexos_graph

        base_url = cls._obter_config()["GRAPH_BASE_URL"]
        url = f"{base_url}/users/{remetente}/sendMail"
        payload = {"message": mensagem, "saveToSentItems": True}

        ultimo_erro = ""
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {cls._obter_token()}",
                        "Content-Type": "application/json",
                    },
                    timeout=TIMEOUT_SEGUNDOS,
                )
                if resposta.status_code == 202:
                    logger.info(
                        "E-mail enviado via Graph para %s (assunto: %s)",
                        [d["emailAddress"]["address"] for d in para],
                        assunto,
                    )
                    return

                ultimo_erro = f"{resposta.status_code}: {resposta.text}"
                if resposta.status_code == 401:
                    cls._token = None  # força renovar o token
                elif resposta.status_code not in (429, 500, 502, 503, 504):
                    break  # erro definitivo (ex.: 403 sem Mail.Send)
            except requests.RequestException as exc:
                ultimo_erro = str(exc)

            logger.warning(
                "Tentativa %s/%s de envio falhou: %s",
                tentativa,
                TENTATIVAS,
                ultimo_erro,
            )
            time.sleep(2**tentativa)

        raise SendEmailGraphError(f"Falha ao enviar e-mail: {ultimo_erro}")


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     # Teste manual: ajuste o destinatário antes de executar.
#     SendEmailGraph.enviar_email(
#         destinatarios=["destinatario@partage.com.br"],
#         assunto="Teste de envio via Graph",
#         corpo_html="<p>Teste de envio via Microsoft Graph.</p>",
#     )