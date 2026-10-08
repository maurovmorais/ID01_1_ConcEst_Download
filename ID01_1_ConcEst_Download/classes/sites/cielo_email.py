"""Download do CSV de relatório da Cielo a partir de e-mails (Microsoft Graph).

Fluxo:
    1. Lê as credenciais genéricas do Windows (Credential Manager).
    2. Obtém token OAuth2 (client credentials) para a Microsoft Graph API.
    3. Busca na Caixa de Entrada as mensagens NÃO LIDAS do remetente/título
       definidos.
    4. Para cada mensagem: baixa o CSV (anexo, se existir; senão pelo link
       "CSV" do corpo do e-mail) para a pasta de destino.
    5. Somente após o download com sucesso, marca a mensagem como lida.

Dependências:
    pip install requests pywin32

Permissões do app no Azure (Application): Mail.ReadWrite
(Mail.Read não basta, pois a mensagem é marcada como lida).
"""

from __future__ import annotations
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings

import base64
import logging
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
import win32cred  # pywin32
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------
USUARIO_EMAIL = InitAllSettings.config['EmailCredenciais']
REMETENTE = "extrato@cielo.com.br"
TITULO = "Cliente Cielo, confira seu relatório recorrente de vendas e recebíveis"
PASTA_DESTINO = Path(InitAllSettings.config['arquivos_baixados'])


CHAVES_CREDENCIAIS = (
    "GRAPH_CLIENT_ID",
    "GRAPH_TENANT_ID",
    "GRAPH_CLIENT_SECRET",
    "GRAPH_BASE_URL",
)
TIMEOUT = 60  # segundos
TAMANHO_PAGINA = 50

logger = logging.getLogger("download_csv_email_graph")


class ErroDownload(Exception):
    """Falha ao localizar ou baixar o CSV de uma mensagem."""


# --------------------------------------------------------------------------
# Credenciais (Windows Credential Manager - Genéricas)
# --------------------------------------------------------------------------
def ler_credencial_windows(chave: str) -> str:
    """Lê o segredo de uma credencial genérica do Windows.

    Args:
        chave: Nome do destino (Target Name) cadastrado no Gerenciador de
            Credenciais.

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

    def _get(self, url: str, params: dict | None = None) -> dict:
        """GET autenticado; renova o token uma vez se expirar (401)."""
        resp = self._sessao.get(
            url, headers=self._headers(), params=params, timeout=TIMEOUT
        )
        if resp.status_code == 401:
            logger.warning("Token expirado; renovando.")
            self.autenticar()
            resp = self._sessao.get(
                url, headers=self._headers(), params=params, timeout=TIMEOUT
            )
        resp.raise_for_status()
        return resp.json()

    def listar_nao_lidas(self, usuario: str, remetente: str) -> list[dict]:
        """Lista mensagens não lidas da Caixa de Entrada de um remetente.

        O filtro por título é feito localmente (ver `titulo_confere`) para
        evitar problemas de acentuação/vírgulas no $filter.
        """
        url = f"{self._base_url}/users/{usuario}/mailFolders/inbox/messages"
        params = {
            "$filter": (
                "isRead eq false and "
                f"from/emailAddress/address eq '{remetente}'"
            ),
            "$select": "id,subject,from,receivedDateTime,hasAttachments,body",
            "$top": TAMANHO_PAGINA,
        }
        mensagens: list[dict] = []
        proxima: str | None = url
        while proxima:
            dados = self._get(proxima, params=params if proxima == url else None)
            mensagens.extend(dados.get("value", []))
            proxima = dados.get("@odata.nextLink")
        logger.info("%d mensagem(ns) não lida(s) de %s.", len(mensagens), remetente)
        return mensagens

    def baixar_anexos_csv(
        self, usuario: str, id_mensagem: str, destino: Path
    ) -> list[Path]:
        """Baixa anexos .csv de uma mensagem (via API direta), se existirem."""
        url = f"{self._base_url}/users/{usuario}/messages/{id_mensagem}/attachments"
        arquivos: list[Path] = []
        for anexo in self._get(url).get("value", []):
            nome = anexo.get("name", "")
            eh_arquivo = anexo.get("@odata.type") == "#microsoft.graph.fileAttachment"
            if not (eh_arquivo and nome.lower().endswith(".csv")):
                continue
            conteudo = base64.b64decode(anexo["contentBytes"])
            arquivos.append(salvar_bytes(conteudo, destino, nome))
        return arquivos

    def marcar_como_lida(self, usuario: str, id_mensagem: str) -> None:
        """Marca a mensagem como lida."""
        url = f"{self._base_url}/users/{usuario}/messages/{id_mensagem}"
        resp = self._sessao.patch(
            url, headers=self._headers(), json={"isRead": True}, timeout=TIMEOUT
        )
        resp.raise_for_status()


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Remove acentos, caixa e espaços extras para comparação de textos."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def titulo_confere(assunto: str) -> bool:
    """Indica se o assunto da mensagem é o título esperado."""
    return normalizar(assunto) == normalizar(TITULO)


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
# Extração do link "CSV" do corpo HTML
# --------------------------------------------------------------------------
class _ExtratorLinks(HTMLParser):
    """Coleta (href, texto) de cada <a>, incluindo o alt de imagens internas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._texto: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if tag == "a" and atributos.get("href"):
            self._href = atributos["href"]
            self._texto = []
        elif tag == "img" and self._href is not None:
            self._texto.append(atributos.get("alt") or "")

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._texto).strip()))
            self._href = None


def extrair_link_csv(html: str) -> str | None:
    """Encontra o link do botão "CSV" no corpo do e-mail.

    Prioridade:
        1. <a> cujo texto (ou alt da imagem) seja "CSV".
        2. <a> cujo href contenha ".csv".
    """
    extrator = _ExtratorLinks()
    extrator.feed(html)

    for href, texto in extrator.links:
        if normalizar(texto) == "csv" and href.lower().startswith("http"):
            return href
    for href, _ in extrator.links:
        if ".csv" in href.lower() and href.lower().startswith("http"):
            return href
    return None


def nome_do_arquivo(resp: requests.Response) -> str:
    """Deduz o nome do arquivo (Content-Disposition > URL final > timestamp)."""
    disposicao = resp.headers.get("Content-Disposition", "")
    achado = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", disposicao, re.I)
    if achado:
        return unquote(achado.group(1))
    nome_url = Path(unquote(urlparse(resp.url).path)).name
    if nome_url.lower().endswith(".csv"):
        return nome_url
    return f"cielo_relatorio_{datetime.now():%Y%m%d_%H%M%S}.csv"


def baixar_csv_do_link(
    sessao: requests.Session, url: str, destino: Path
) -> Path:
    """Baixa o CSV apontado pelo link do e-mail.

    Raises:
        ErroDownload: Se a resposta for uma página HTML (link expirado/login).
    """
    destino.mkdir(parents=True, exist_ok=True)
    with sessao.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        tipo = resp.headers.get("Content-Type", "").lower()
        if "text/html" in tipo:
            raise ErroDownload(
                "O link retornou uma página HTML (expirado ou exige login)."
            )
        caminho = caminho_unico(destino, nome_do_arquivo(resp))
        parcial = caminho.with_suffix(caminho.suffix + ".part")
        try:
            with parcial.open("wb") as arquivo:
                for bloco in resp.iter_content(chunk_size=1024 * 64):
                    arquivo.write(bloco)
            parcial.replace(caminho)
        finally:
            parcial.unlink(missing_ok=True)
    logger.info("Arquivo baixado: %s", caminho)
    return caminho


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------
def processar_mensagem(
    graph: GraphClient, sessao: requests.Session, mensagem: dict
) -> list[Path]:
    """Baixa o(s) CSV(s) de uma mensagem e a marca como lida.

    Returns:
        Lista de arquivos baixados.

    Raises:
        ErroDownload: Se nenhum CSV puder ser obtido.
    """
    id_msg = mensagem["id"]
    assunto = mensagem.get("subject", "")
    logger.info("Processando: %s (%s)", assunto, mensagem.get("receivedDateTime"))

    arquivos: list[Path] = []

    # 1) Forma direta via API: anexos .csv (se existirem)
    if mensagem.get("hasAttachments"):
        arquivos = graph.baixar_anexos_csv(USUARIO_EMAIL, id_msg, PASTA_DESTINO)

    # 2) Link "CSV" do corpo do e-mail
    if not arquivos:
        html = (mensagem.get("body") or {}).get("content", "")
        link = extrair_link_csv(html)
        if not link:
            raise ErroDownload("Link do botão CSV não encontrado no corpo.")
        arquivos = [baixar_csv_do_link(sessao, link, PASTA_DESTINO)]

    graph.marcar_como_lida(USUARIO_EMAIL, id_msg)
    logger.info("Mensagem marcada como lida.")
    return arquivos


def buscar_arquivos_email() -> int:
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
                processar_mensagem(graph, sessao, mensagem)
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
#     raise SystemExit(buscar_arquivos_email())