"""Função de login no Portal Estabelecimentos Comerciais (ConectCar).

Reutiliza a instância do Chrome/WebDriver já iniciada pela automação
(o driver deve ser criado e passado por quem chama esta função —
nenhuma nova janela de navegador é aberta aqui).
"""

import logging
import time
import zipfile
from pathlib import Path
import shutil

from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys

from ID01_1_ConcEst_Download.classes.utils.CredentialWindows import obter_credencial_windows
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings
from ID01_1_ConcEst_Download.classes.utils.util_data import obter_intervalo_ontem,obter_data_ontem

logger = logging.getLogger(__name__)

URL_LOGIN = ('https://conveniado.conectcar.com/Autenticacao/Autenticar?ReturnUrl=%2f')
NOME_CREDENCIAL_WINDOWS = "site_conectcar"
USUARIO = InitAllSettings.config['usuarios']
SELETOR_CAMPO_EMAIL = (By.XPATH,'//*[@id="UserName"]')
XPATH_BOTAO_OK_RELATORIO = (
    "//div[contains(@class, 'redesign__modal__content__info')]"
    "//div[contains(@class, 'botoes')]"
    "//button[normalize-space(text())='Ok']")
XPATH_PRIMEIRA_LINHA = ("//table[@id='ResultadoTransacoes']/tbody/tr[1]")
XPATH_LINK_DOWNLOAD_NA_LINHA = ".//a[normalize-space(text())='Download']"
XPATH_LINK_PROCESSANDO_NA_LINHA = ".//a[@processando='true']"
PREFIXO_PASTA_EXTRAIDA = "Transacoes_"

#Tempos e dalays
TIMEOUT_PADRAO_SEGUNDOS = 20
TENTATIVAS_MAXIMAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 3
TIMEOUT_PADRAO = 30
TIMEOUT_DOWNLOAD_PADRAO = 420  # relatório pode levar minutos p/ processar
INTERVALO_POLL = 5


def fazer_login_conectcar(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS,
    tentativas_maximas: int = TENTATIVAS_MAXIMAS,
) -> None:
    """Realiza o login no Portal Estabelecimentos Comerciais (Sem Parar).

    Usuário e senha são recuperados do Gerenciador de Credenciais do
    Windows (credencial "site_conectcar)"). Utiliza a instância de Chrome já
    aberta (o ``driver`` recebido por parâmetro), sem abrir um novo
    navegador.

    Args:
        driver: Instância do WebDriver (Chrome) já iniciada pela automação.
        timeout: Tempo máximo, em segundos, de espera por cada elemento.
        tentativas_maximas: Número máximo de tentativas em caso de falha
            recuperável (ex.: elemento ainda não carregado).

    Raises:
        ValueError: Se a credencial do Windows não for encontrada/estiver
            incompleta.
        TimeoutException: Se os elementos da página não aparecerem dentro
            do tempo esperado, mesmo após todas as tentativas.
    """
    usuario, senha = obter_credencial_windows(NOME_CREDENCIAL_WINDOWS)

    ultima_excecao: Exception | None = None

    for tentativa in range(1, tentativas_maximas + 1):
        try:
            logger.info(
                "Tentativa %d/%d de login no Portal Conectcar.",
                tentativa,
                tentativas_maximas,
            )
            driver.get(URL_LOGIN)

            # Maximiza a tela imediatamente depois
            driver.maximize_window()
            time.sleep(3)
            
            espera = WebDriverWait(driver, timeout)

            campo_email = espera.until(
                EC.visibility_of_element_located(SELETOR_CAMPO_EMAIL)
            )
            # Preencher o usuario
            email_usuario = driver.find_element(By.XPATH,'//*[@id="UserName"]')
            email_usuario.send_keys(USUARIO)
            
            # Preencher a senha
            senha_usuario = driver.find_element(By.XPATH,'//*[@id="Password"]')
            senha_usuario.send_keys(senha)
            time.sleep(2)

            #Não sou um robô
            ##TODO colocar um anticaptcha aqui
            print('Fazer manualmente')

            # Clicar em entrar
            botao_entrar = driver.find_element(By.XPATH,'//*[@id="FormAutenticar"]/div/div/article/section/div/div/div[2]/div[5]/input')
            botao_entrar.click()


            # Confirma que o login foi bem-sucedido aguardando a URL sair
            # da tela de login (ajustar condição conforme comportamento
            # real do site, ex.: aguardar um elemento exclusivo do home).
            espera.until(lambda d: "login" not in d.current_url.lower())

            logger.info("Login no Portal ConectCar realizado com sucesso.")
            return

        except (
            TimeoutException,
            NoSuchElementException,
            ElementNotInteractableException,
        ) as exc:
            ultima_excecao = exc
            logger.warning(
                "Falha na tentativa %d/%d de login: %s",
                tentativa,
                tentativas_maximas,
                exc,
            )
            if tentativa < tentativas_maximas:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_SEGUNDOS)

    logger.error(
        "Login no Portal Veloe falhou após %d tentativas.",
        tentativas_maximas,
    )
    raise TimeoutException(
        f"Não foi possível realizar login após {tentativas_maximas} "
        "tentativas."
    ) from ultima_excecao




def navegar_aba_transacoes(driver: WebDriver) -> None:
    """
    Navega até a aba Estadia do Taggy

    """
    try:
        #Navega para a Tela
        driver.get('https://conveniado.conectcar.com/Transacao/ConsultarTransacaoEstacionamento')
        
        try:
        #Fechar Popup
            time.sleep(2)
            campo_popup = driver.find_element(By.XPATH,'/html/body/div[6]/div[1]/button/span[1]')
            campo_popup.click()
        except:
            pass
        
        #Selecionar Campo Buscar Conveniados e selecionar TODOS
        time.sleep(2)
        campo_buscar = driver.find_element(By.XPATH,'//*[@id="visao-grupo--input"]')
        campo_buscar.click()
        time.sleep(0.5)
        check_todos = driver.find_element(By.XPATH,'/html/body/div[1]/div[1]/article/section/form/div/div/section/div[2]/div/div/div/ul/li[1]/label/span')
        check_todos.click()
        
        #Chama a função para obter o texto
        texto_para_campo = obter_data_ontem()
        
        #Preenche campo data inicial
        campo_data_inicial = driver.find_element(By.XPATH,'//*[@id="DataInicial"]')
        campo_data_inicial.send_keys(texto_para_campo)

        #Preenche campo data final
        campo_data_final = driver.find_element(By.XPATH,'//*[@id="DataFinal"]')
        campo_data_final.send_keys(texto_para_campo)

        #Pesquisar
        botao_pesquisar= driver.find_element(By.XPATH,'/html/body/div[1]/div[1]/article/section/form/div/div/div[3]/input')
        botao_pesquisar.click()

        #Tela POPUP Relatorio solicitado com sucesso
        fechar_modal_relatorio_solicitado(driver)
        time.sleep(1)

        #Navega para a Tela
        driver.get('https://conveniado.conectcar.com/CentralArquivos')
        time.sleep(0.5)

        #Baixar Relatorio
        baixar_primeiro_arquivo_quando_pronto(driver)
        time.sleep(3)

        #Descompactar arquivo .zip
        
        pasta_raiz = caminho_arquivo_baixado = InitAllSettings.config['arquivos_baixados']
        caminho_arquivo_baixado = localizar_zip_mais_recente(caminho_arquivo_baixado)
        descompactar_arquivo(caminho_arquivo_baixado)
        arquivos_movidos = mover_arquivos_extraidos_para_raiz(pasta_raiz, caminho_arquivo_baixado)

        print()

    except Exception as err:
        Log.write_log(f"Falha no Download - Erro: {err}")
        raise


def fechar_modal_relatorio_solicitado(
    driver: WebDriver, timeout: int = TIMEOUT_PADRAO
) -> None:
    """Clica no botão 'Ok' do popup de sucesso 'Relatório solicitado'.

    Args:
        driver: instância do WebDriver do Selenium já posicionada na
            página onde o popup está visível.
        timeout: tempo máximo (em segundos) de espera pelo botão
            ficar clicável.

    Raises:
        TimeoutException: se o botão não aparecer/ficar clicável
            dentro do tempo definido.
    """
    try:
        botao_ok = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_OK_RELATORIO))
        )
        botao_ok.click()
        logger.info("Popup 'Relatório solicitado' fechado com sucesso.")
    except TimeoutException:
        logger.error(
            "Botão 'Ok' do popup 'Relatório solicitado' não ficou "
            "clicável em %s segundos.",
            timeout,
        )
        raise
    except ElementClickInterceptedException:
        logger.warning(
            "Clique interceptado no botão 'Ok'; tentando via JavaScript."
        )
        driver.execute_script("arguments[0].click();", botao_ok)


def _download_disponivel_na_primeira_linha(
    driver: WebDriver,
) -> WebElement | bool:
    """Expected condition: retorna o link de Download quando disponível.

    Enquanto a linha estiver com o link 'Processando'
    (atributo processando="true"), retorna False para o
    WebDriverWait continuar aguardando.
    """
    try:
        linha = driver.find_element(By.XPATH, XPATH_PRIMEIRA_LINHA)
    except Exception:
        return False

    if linha.find_elements(By.XPATH, XPATH_LINK_PROCESSANDO_NA_LINHA):
        return False

    links_download = linha.find_elements(
        By.XPATH, XPATH_LINK_DOWNLOAD_NA_LINHA
    )
    return links_download[0] if links_download else False


def baixar_primeiro_arquivo_quando_pronto(
    driver: WebDriver,
    timeout: int = TIMEOUT_DOWNLOAD_PADRAO,
) -> None:
    """Aguarda o status da primeira linha da Central de Arquivos sair
    de 'Processando' para 'Download' e clica no link.

    Args:
        driver: instância do WebDriver já posicionada na tela
            'Central de arquivos'.
        timeout: tempo máximo (em segundos) de espera pelo
            processamento do relatório terminar.

    Raises:
        TimeoutException: se o relatório não terminar de processar
            dentro do tempo definido.
    """
    try:
        link_download = WebDriverWait(
            driver, timeout, poll_frequency=INTERVALO_POLL
        ).until(_download_disponivel_na_primeira_linha)
        link_download.click()
        logger.info(
            "Download da primeira linha da Central de Arquivos iniciado."
        )
    except TimeoutException:
        logger.error(
            "Relatório não ficou disponível para download em %s "
            "segundos.",
            timeout,
        )
        raise


def descompactar_arquivo(
    caminho_arquivo_baixado: str | Path,
    pasta_destino: str | Path | None = None,
) -> Path:
    """Descompacta um arquivo .zip para uma pasta de destino.

    Args:
        caminho_arquivo_baixado: caminho completo do arquivo .zip
            baixado (str ou Path).
        pasta_destino: pasta onde os arquivos serão extraídos. Se
            não informado, extrai para uma pasta com o mesmo nome
            do .zip (sem extensão), no mesmo diretório do arquivo.

    Returns:
        Path da pasta onde os arquivos foram extraídos.

    Raises:
        FileNotFoundError: se o arquivo .zip não existir.
        zipfile.BadZipFile: se o arquivo não for um .zip válido ou
            estiver corrompido.
    """
    caminho_arquivo_baixado = Path(caminho_arquivo_baixado)

    if not caminho_arquivo_baixado.exists():
        logger.error(
            "Arquivo .zip não encontrado: %s", caminho_arquivo_baixado
        )
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho_arquivo_baixado}"
        )

    if pasta_destino is None:
        pasta_destino = caminho_arquivo_baixado.with_suffix("")
    else:
        pasta_destino = Path(pasta_destino)

    pasta_destino.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(caminho_arquivo_baixado, "r") as arquivo_zip:
            arquivo_zip.extractall(pasta_destino)
        logger.info(
            "Arquivo %s descompactado em %s",
            caminho_arquivo_baixado.name,
            pasta_destino,
        )
    except zipfile.BadZipFile:
        logger.error(
            "Arquivo .zip inválido ou corrompido: %s",
            caminho_arquivo_baixado,
        )
        raise

    return pasta_destino


def localizar_zip_mais_recente(pasta_downloads: str | Path) -> Path:
    """Localiza o arquivo .zip mais recente dentro de uma pasta.

    Útil quando o nome do arquivo baixado é dinâmico (ex.:
    Transacoes_20260914_12450004540.zip).

    Args:
        pasta_downloads: pasta onde o(s) arquivo(s) .zip foram
            baixados.

    Returns:
        Path do arquivo .zip mais recente encontrado na pasta.

    Raises:
        NotADirectoryError: se pasta_downloads não for uma pasta.
        FileNotFoundError: se nenhum arquivo .zip for encontrado.
    """
    pasta_downloads = Path(pasta_downloads)

    if not pasta_downloads.is_dir():
        logger.error(
            "Caminho informado não é uma pasta: %s", pasta_downloads
        )
        raise NotADirectoryError(
            f"Caminho informado não é uma pasta: {pasta_downloads}"
        )

    arquivos_zip = list(pasta_downloads.glob("*.zip"))

    if not arquivos_zip:
        logger.error(
            "Nenhum arquivo .zip encontrado em: %s", pasta_downloads
        )
        raise FileNotFoundError(
            f"Nenhum arquivo .zip encontrado em: {pasta_downloads}"
        )

    arquivo_mais_recente = max(
        arquivos_zip, key=lambda arquivo: arquivo.stat().st_mtime
    )
    logger.info(
        "Arquivo .zip mais recente localizado: %s", arquivo_mais_recente
    )
    return arquivo_mais_recente


def mover_arquivos_extraidos_para_raiz(
    pasta_raiz: str | Path,
    caminho_arquivo_zip: str | Path,
    prefixo_pasta: str = PREFIXO_PASTA_EXTRAIDA,
) -> list[Path]:
    """Move os arquivos de dentro da pasta extraída (ex.: Transacoes_*)
    para a raiz de Arquivos_Baixados, removendo em seguida a pasta
    extraída (vazia) e o arquivo .zip original.

    Args:
        pasta_raiz: pasta raiz onde está a subpasta extraída
            (ex.: C:\\Armazenamento\\ID01_1_ConcEst_Download\\Arquivos_Baixados).
        caminho_arquivo_zip: caminho do arquivo .zip original, a ser
            removido após a movimentação dos arquivos.
        prefixo_pasta: prefixo do nome da subpasta extraída a ser
            localizada dentro de pasta_raiz.

    Returns:
        Lista de Paths dos arquivos movidos para a raiz.

    Raises:
        NotADirectoryError: se pasta_raiz não for uma pasta.
        FileNotFoundError: se nenhuma subpasta com o prefixo
            informado for encontrada.
    """
    pasta_raiz = Path(pasta_raiz)
    caminho_arquivo_zip = Path(caminho_arquivo_zip)

    if not pasta_raiz.is_dir():
        logger.error("Caminho informado não é uma pasta: %s", pasta_raiz)
        raise NotADirectoryError(
            f"Caminho informado não é uma pasta: {pasta_raiz}"
        )

    subpastas_extraidas = [
        item
        for item in pasta_raiz.iterdir()
        if item.is_dir() and item.name.startswith(prefixo_pasta)
    ]

    if not subpastas_extraidas:
        logger.error(
            "Nenhuma pasta extraída com prefixo '%s' encontrada em: %s",
            prefixo_pasta,
            pasta_raiz,
        )
        raise FileNotFoundError(
            f"Nenhuma pasta extraída com prefixo '{prefixo_pasta}' "
            f"encontrada em: {pasta_raiz}"
        )

    pasta_extraida = max(
        subpastas_extraidas, key=lambda pasta: pasta.stat().st_mtime
    )

    arquivos_movidos: list[Path] = []
    for arquivo in pasta_extraida.iterdir():
        if not arquivo.is_file():
            continue
        destino = pasta_raiz / arquivo.name
        shutil.move(str(arquivo), str(destino))
        arquivos_movidos.append(destino)
        logger.info("Arquivo movido: %s -> %s", arquivo.name, destino)

    # Remove a pasta extraída, se estiver vazia
    try:
        pasta_extraida.rmdir()
        logger.info("Pasta extraída removida: %s", pasta_extraida)
    except OSError:
        logger.warning(
            "Pasta extraída não foi removida (não está vazia?): %s",
            pasta_extraida,
        )

    # Remove o .zip original
    if caminho_arquivo_zip.exists():
        caminho_arquivo_zip.unlink()
        logger.info("Arquivo .zip removido: %s", caminho_arquivo_zip)
    else:
        logger.warning(
            "Arquivo .zip não encontrado para remoção: %s",
            caminho_arquivo_zip,
        )

    return arquivos_movidos

