"""Download dos anexos do e-mail "Arquivo Retorno Bradesco PIX" (Graph API).

Módulo autônomo: não depende de outros arquivos do projeto.

Fluxo:
    1. Lê as credenciais genéricas do Windows (Credential Manager).
    2. Autentica na Graph API (client credentials).
    3. Busca na Caixa de Entrada mensagens NÃO LIDAS do remetente/título.
    4. Baixa todos os anexos de arquivo (ignora imagens inline).
    5. Só após baixar tudo com sucesso, marca a mensagem como lida.

Dependências:
    pip install requests pywin32

Permissão do app no Azure (Application): Mail.ReadWrite.
"""

from __future__ import annotations
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings

import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
import win32cred  # pywin32
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------
USUARIO_EMAIL = InitAllSettings.config['EmailCredenciais']
REMETENTE = "automacao@partage.com.br"
TITULO = "Arquivo Retorno Bradesco PIX"
# Pasta de destino assumida igual à da automação da Cielo; ajuste se precisar.
PASTA_DESTINO = Path(InitAllSettings.config['arquivos_baixados'])

CHAVES_CREDENCIAIS = (
    "GRAPH_CLIENT_ID",
    "GRAPH_TENANT_ID",
    "GRAPH_CLIENT_SECRET",
    "GRAPH_BASE_URL",
)
TIMEOUT = 60  # segundos
TAMANHO_PAGINA = 50

logger = logging.getLogger("bradesco_email")


class ErroDownload(Exception):
    """Falha ao localizar ou baixar o anexo de uma mensagem."""


# --------------------------------------------------------------------------
# Credenciais (Windows Credential Manager - Genéricas)
# --------------------------------------------------------------------------
def ler_credencial_windows(chave: str) -> str:
    """Lê o segredo de uma credencial genérica do Windows.

    Args:
        chave: Nome do destino (Target Name) no Gerenciador de Credenciais.

    Returns:
        O valor (senha) armazenado.

    Raises:
        RuntimeError: Se a credencial não existir ou estiver vazia.
    """
    try:
        cred = win32cred.CredRead(chave, win32cred.CRED_TYPE_GENERIC, 0)
    except Exception as exc:  # pywintypes.error não é importável de forma estável
        raise RuntimeError(f"Credencial do Windows não encontrada: {chave}") from exc

    blob = cred["CredentialBlob"]
    valor = blob.decode("utf-16-le") if isinstance(blob, bytes) else str(blob)
    valor = valor.strip()
    if not valor:
        raise RuntimeError(f"Credencial do Windows vazia: {chave}")
    return valor


def carregar_credenciais() -> dict[str, str]:
    """Carrega todas as credenciais necessárias do Windows."""
    return {chave: ler_credencial_windows(chave) for chave in CHAVES_CREDENCIAIS}


# --------------------------------------------------------------------------
# Sessão HTTP com retry/backoff
# --------------------------------------------------------------------------
def criar_sessao() -> requests.Session:
    """Cria uma sessão com retry exponencial para erros transitórios."""
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST", "PATCH"}),
        respect_retry_after_header=True,
    )
    sessao = requests.Session()
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Remove acentos, caixa e espaços extras para comparação de textos."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def titulo_confere(assunto: str) -> bool:
    """Indica se o assunto começa com o título esperado.

    O assunto real traz um sufixo após o título (ex.: "... PIX - <data>"),
    por isso a comparação é por prefixo, ignorando acento e caixa.
    """
    return normalizar(assunto).startswith(normalizar(TITULO))


def nome_seguro(nome: str) -> str:
    """Remove caracteres inválidos para nome de arquivo no Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" .") or "arquivo"


def caminho_unico(pasta: Path, nome: str) -> Path:
    """Evita sobrescrever: acrescenta timestamp se o arquivo já existir."""
    caminho = pasta / nome_seguro(nome)
    if caminho.exists():
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = caminho.with_name(f"{caminho.stem}_{carimbo}{caminho.suffix}")
    return caminho


def salvar_bytes(conteudo: bytes, pasta: Path, nome: str) -> Path:
    """Salva bytes na pasta de destino sem sobrescrever arquivos existentes."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = caminho_unico(pasta, nome)
    caminho.write_bytes(conteudo)
    logger.info("Arquivo salvo: %s", caminho)
    return caminho


# --------------------------------------------------------------------------
# Cliente Graph
# --------------------------------------------------------------------------
class GraphClient:
    """Cliente mínimo da Microsoft Graph API (client credentials)."""

    def __init__(self, credenciais: dict[str, str], sessao: requests.Session) -> None:
        self._tenant_id = credenciais["GRAPH_TENANT_ID"]
        self._client_id = credenciais["GRAPH_CLIENT_ID"]
        self._client_secret = credenciais["GRAPH_CLIENT_SECRET"]
        self._base_url = credenciais["GRAPH_BASE_URL"].rstrip("/")
        self._sessao = sessao
        self._token: str | None = None

    def autenticar(self) -> None:
        """Obtém o access token da aplicação."""
        url = (
            f"https://login.microsoftonline.com/{self._tenant_id}"
            "/oauth2/v2.0/token"
        )
        resp = self._sessao.post(
            url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        logger.info("Autenticado na Graph API.")

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise RuntimeError("Cliente não autenticado.")
        return {"Authorization": f"Bearer {self._token}"}

    def _requisitar(
        self, metodo: str, url: str, **kwargs
    ) -> requests.Response:
        """Requisição autenticada; renova o token uma vez se expirar (401)."""
        resp = self._sessao.request(
            metodo, url, headers=self._headers(), timeout=TIMEOUT, **kwargs
        )
        if resp.status_code == 401:
            logger.warning("Token expirado; renovando.")
            self.autenticar()
            resp = self._sessao.request(
                metodo, url, headers=self._headers(), timeout=TIMEOUT, **kwargs
            )
        resp.raise_for_status()
        return resp

    def listar_nao_lidas(self, usuario: str, remetente: str) -> list[dict]:
        """Lista mensagens não lidas da Caixa de Entrada de um remetente.

        O filtro por título é feito localmente (ver `titulo_confere`).
        """
        url = f"{self._base_url}/users/{usuario}/mailFolders/inbox/messages"
        params = {
            "$filter": (
                "isRead eq false and "
                f"from/emailAddress/address eq '{remetente}'"
            ),
            "$select": "id,subject,from,receivedDateTime,hasAttachments",
            "$top": TAMANHO_PAGINA,
        }
        mensagens: list[dict] = []
        proxima: str | None = url
        while proxima:
            resp = self._requisitar(
                "GET", proxima, params=params if proxima == url else None
            )
            dados = resp.json()
            mensagens.extend(dados.get("value", []))
            proxima = dados.get("@odata.nextLink")
        logger.info("%d mensagem(ns) não lida(s) de %s.", len(mensagens), remetente)
        return mensagens

    def baixar_todos_anexos(
        self, usuario: str, id_mensagem: str, destino: Path
    ) -> list[Path]:
        """Baixa todos os anexos de arquivo (não inline) de uma mensagem.

        Usa o endpoint `/$value` (conteúdo bruto), que funciona também para
        anexos grandes.
        """
        base = f"{self._base_url}/users/{usuario}/messages/{id_mensagem}/attachments"
        arquivos: list[Path] = []
        for anexo in self._requisitar("GET", base).json().get("value", []):
            eh_arquivo = anexo.get("@odata.type") == "#microsoft.graph.fileAttachment"
            if not eh_arquivo or anexo.get("isInline"):
                continue
            resp = self._requisitar("GET", f"{base}/{anexo['id']}/$value")
            arquivos.append(salvar_bytes(resp.content, destino, anexo["name"]))
        return arquivos

    def marcar_como_lida(self, usuario: str, id_mensagem: str) -> None:
        """Marca a mensagem como lida."""
        url = f"{self._base_url}/users/{usuario}/messages/{id_mensagem}"
        self._requisitar("PATCH", url, json={"isRead": True})


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------
def processar_mensagem(graph: GraphClient, mensagem: dict) -> list[Path]:
    """Baixa os anexos de uma mensagem e a marca como lida.

    Raises:
        ErroDownload: Se a mensagem não tiver nenhum anexo de arquivo.
    """
    id_msg = mensagem["id"]
    logger.info(
        "Processando: %s (%s)", mensagem.get("subject"), mensagem.get("receivedDateTime")
    )
    arquivos = graph.baixar_todos_anexos(USUARIO_EMAIL, id_msg, PASTA_DESTINO)
    if not arquivos:
        raise ErroDownload("Nenhum anexo de arquivo encontrado na mensagem.")

    graph.marcar_como_lida(USUARIO_EMAIL, id_msg)
    logger.info("%d anexo(s) baixado(s); mensagem marcada como lida.", len(arquivos))
    return arquivos


def buscar_email_bradesco() -> int:
    """Ponto de entrada. Retorna 0 em sucesso e 1 se houve falhas."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sessao = criar_sessao()
    try:
        graph = GraphClient(carregar_credenciais(), sessao)
        graph.autenticar()

        candidatas = [
            m
            for m in graph.listar_nao_lidas(USUARIO_EMAIL, REMETENTE)
            if titulo_confere(m.get("subject", ""))
        ]
        logger.info("%d mensagem(ns) com o título esperado.", len(candidatas))

        falhas = 0
        for mensagem in sorted(candidatas, key=lambda m: m["receivedDateTime"]):
            try:
                processar_mensagem(graph, mensagem)
            except (ErroDownload, requests.RequestException, OSError):
                # Não marca como lida: será reprocessada na próxima execução.
                logger.exception("Falha ao processar a mensagem %s.", mensagem["id"])
                falhas += 1
        return 1 if falhas else 0
    except Exception:
        logger.exception("Erro fatal na automação.")
        return 1
    finally:
        sessao.close()


# if __name__ == "__main__":
#     raise SystemExit(buscar_email_bradesco())