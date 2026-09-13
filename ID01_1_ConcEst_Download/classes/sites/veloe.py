"""Função de login no Portal Estabelecimentos Comerciais (Veloe).

Reutiliza a instância do Chrome/WebDriver já iniciada pela automação
(o driver deve ser criado e passado por quem chama esta função —
nenhuma nova janela de navegador é aberta aqui).
"""

import logging
import time

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

from ID01_1_ConcEst_Download.classes.utils.CredentialWindows import obter_credencial_windows
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings

logger = logging.getLogger(__name__)

URL_LOGIN = (
    "https://beta-portal-ec.veloe.com.br/portalec-shell-frt/login"
    "?returnUrl=home"
)
NOME_CREDENCIAL_WINDOWS = "site_Veloe"

USUARIO = InitAllSettings.config['usuarios']

# Seletores
SELETOR_CAMPO_EMAIL = (By.XPATH, '//*[@id="username"]')
SELETOR_CAMPO_SENHA = (By.XPATH, '//*[@id="password"]')
SELETOR_BOTAO_ENTRAR = (By.XPATH, '/html/body/app-root/app-page-login/app-template-login/div/div[2]/section/form/div[2]/vlv-button')
SELETOR_BOTAO_BUSCAR = (By.XPATH,'/html/body/app-root/app-authenticated-layout/app-consultas/main/div/div/section/app-view-lancamentos/main/section[1]/form/div[4]/vlv-button')
SELETOR_BOTAO_DOWNLOAD_1 = (By.XPATH,'/html/body/app-root/app-authenticated-layout/app-consultas/main/div/div/section/app-view-lancamentos/main/section[2]/app-tabela-lancamentos/div/header/div/vlv-tooltip/vlv-button-icon')
SELETOR_CELULA_STATUS_PRIMEIRA_LINHA = (By.XPATH,"(//tr[contains(@class, 'vlv-table-line-content')])[1]/td[4]/vlv-table-cel-content",)
SELETOR_ICONE_DOWNLOAD_PRIMEIRA_LINHA = (By.XPATH,"(//tr[contains(@class, 'vlv-table-line-content')])[1]/td[5]/vlv-table-cel-content/vlv-button-icon",)

#Tempos e dalays
TIMEOUT_PADRAO_SEGUNDOS = 20
TENTATIVAS_MAXIMAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 3
STATUS_SUCESSO = "Sucesso"
TIMEOUT_AGUARDAR_RELATORIO_SEGUNDOS = 300
INTERVALO_VERIFICACAO_SEGUNDOS = 5


def fazer_login_veloe(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS,
    tentativas_maximas: int = TENTATIVAS_MAXIMAS,
) -> None:
    """Realiza o login no Portal Estabelecimentos Comerciais (Veloe).

    Usuário e senha são recuperados do Gerenciador de Credenciais do
    Windows (credencial "site_Veloe"). Utiliza a instância de Chrome já
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
                "Tentativa %d/%d de login no Portal Veloe.",
                tentativa,
                tentativas_maximas,
            )
            driver.get(URL_LOGIN)

            # 2. Maximiza a tela imediatamente depois
            driver.maximize_window()
            time.sleep(3)
            
            espera = WebDriverWait(driver, timeout)

            campo_email = espera.until(
                EC.visibility_of_element_located(SELETOR_CAMPO_EMAIL)
            )
            #Preencher o usuario
            wrapper_email = espera.until(EC.presence_of_element_located(SELETOR_CAMPO_EMAIL))
            _preencher_input_shadow(driver, wrapper_email, USUARIO)
            
            #Preencher a senha
            wrapper_senha = espera.until(EC.presence_of_element_located(SELETOR_CAMPO_SENHA))
            _preencher_input_shadow(driver, wrapper_senha, senha)

            
            #Precisa clicar nos dois campos antes de clicar em entrar(bug do site)
            wrapper_botao = espera.until(EC.presence_of_element_located(SELETOR_CAMPO_EMAIL))
            _clicar_componente(driver, wrapper_botao)
            wrapper_botao = espera.until(EC.presence_of_element_located(SELETOR_CAMPO_SENHA))
            _clicar_componente(driver, wrapper_botao)

            # Clicar em entrar
            wrapper_botao = espera.until(EC.presence_of_element_located(SELETOR_BOTAO_ENTRAR))
            _clicar_componente(driver, wrapper_botao)


            # Confirma que o login foi bem-sucedido aguardando a URL sair
            # da tela de login (ajustar condição conforme comportamento
            # real do site, ex.: aguardar um elemento exclusivo do home).
            espera.until(lambda d: "login" not in d.current_url.lower())

            logger.info("Login no Portal Veloe realizado com sucesso.")
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


def _preencher_input_shadow(
    driver: WebDriver, wrapper: WebElement, valor: str
) -> None:
    """Preenche o <input> dentro do Shadow DOM de um componente customizado
    via JavaScript (mais confiável que a API shadow_root do Selenium).
    """
    input_encontrado = driver.execute_script(
        """
        const host = arguments[0];
        const root = host.shadowRoot;
        if (!root) { return null; }
        return root.querySelector('input');
        """,
        wrapper,
    )

    if input_encontrado is None:
        raise NoSuchElementException(
            "Não foi possível localizar <input> no shadow DOM de "
            f"'{wrapper.get_attribute('id')}'. Pode ser shadow DOM "
            "fechado (closed) ou o input estar mais aninhado."
        )

    driver.execute_script(
        """
        const input = arguments[0];
        input.value = arguments[1];
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        input_encontrado,
        valor,
    )


def _clicar_componente(driver: WebDriver, wrapper: WebElement) -> None:
    """Clica em um web component customizado (ex.: <vlv-button>).

    Tenta primeiro o clique direto no elemento host (funciona quando o
    componente propaga o evento de clique). Se não disparar nada útil,
    cai para localizar e clicar no <button>/elemento clicável dentro do
    Shadow DOM via JavaScript.
    """
    try:
        wrapper.click()
        return
    except (ElementClickInterceptedException, ElementNotInteractableException):
        logger.debug(
            "Clique direto no host '%s' falhou, tentando via shadow DOM.",
            wrapper.get_attribute("id") or wrapper.tag_name,
        )

    clicado = driver.execute_script(
        """
        const host = arguments[0];
        const root = host.shadowRoot;
        if (!root) { return false; }
        const alvo = root.querySelector('button, [role="button"], a');
        if (!alvo) { return false; }
        alvo.click();
        return true;
        """,
        wrapper,
    )

    if not clicado:
        raise NoSuchElementException(
            "Não foi possível clicar no componente "
            f"'{wrapper.get_attribute('id') or wrapper.tag_name}' "
            "(nem no host, nem em elemento clicável do shadow DOM)."
        )

def _ler_texto_shadow(driver: WebDriver, componente: WebElement) -> str:
    """Lê o texto renderizado dentro do Shadow DOM de um componente
    customizado (ex.: <vlv-table-cel-content>).

    Args:
        driver: Instância do WebDriver.
        componente: Elemento host do web component a ser lido.

    Returns:
        Texto renderizado dentro do Shadow DOM (ou do DOM leve, como
        fallback, se o componente não tiver Shadow DOM).
    """
    texto = driver.execute_script(
        """
        const host = arguments[0];
        const root = host.shadowRoot;
        return root ? root.textContent : host.textContent;
        """,
        componente,
    )
    return (texto or "").strip()

def _ler_texto_shadow_profundo(driver: WebDriver, elemento: WebElement) -> str:
    """Lê texto de um elemento atravessando recursivamente qualquer
    profundidade de Shadow DOM aninhado (necessário quando um componente
    customizado contém outro componente customizado dentro dele).
    """
    texto = driver.execute_script(
        """
        function coletarTexto(no) {
            if (no.shadowRoot) {
                return coletarTexto(no.shadowRoot);
            }
            let resultado = '';
            for (const filho of no.childNodes) {
                if (filho.nodeType === Node.TEXT_NODE) {
                    resultado += filho.textContent;
                } else if (filho.nodeType === Node.ELEMENT_NODE) {
                    resultado += coletarTexto(filho);
                }
            }
            return resultado;
        }
        return coletarTexto(arguments[0]);
        """,
        elemento,
    )
    return (texto or "").strip()

def _buscar_shadow_profundo(driver: WebDriver, seletor_css: str) -> WebElement | None:
    """Busca um elemento por seletor CSS, atravessando recursivamente
    qualquer nível de Shadow DOM (necessário porque XPath e find_element
    normais não enxergam dentro de shadow roots).

    Args:
        driver: Instância do WebDriver.
        seletor_css: Seletor CSS do elemento procurado (ex.: "tr.minha-classe").

    Returns:
        O WebElement encontrado, ou None se não existir em nenhum nível.
    """
    return driver.execute_script(
        """
        function buscarProfundo(seletorCss, raiz) {
            raiz = raiz || document;
            let encontrado = raiz.querySelector(seletorCss);
            if (encontrado) { return encontrado; }
            const todosElementos = raiz.querySelectorAll('*');
            for (const el of todosElementos) {
                if (el.shadowRoot) {
                    encontrado = buscarProfundo(seletorCss, el.shadowRoot);
                    if (encontrado) { return encontrado; }
                }
            }
            return null;
        }
        return buscarProfundo(arguments[0]);
        """,
        seletor_css,
    )

def _buscar_primeira_linha_com_dados(
    driver: WebDriver, seletor_css: str
) -> WebElement | None:
    """Busca, em qualquer nível de Shadow DOM, a primeira ocorrência de
    seletor_css que tenha ao menos um elemento filho — pulando linhas
    "molde"/placeholder vazias que compartilham a mesma classe CSS.
    """
    return driver.execute_script(
        """
        function coletarProfundo(seletorCss, raiz, resultado) {
            raiz = raiz || document;
            resultado = resultado || [];
            raiz.querySelectorAll(seletorCss).forEach(el => resultado.push(el));
            const todosElementos = raiz.querySelectorAll('*');
            for (const el of todosElementos) {
                if (el.shadowRoot) {
                    coletarProfundo(seletorCss, el.shadowRoot, resultado);
                }
            }
            return resultado;
        }
        const linhas = coletarProfundo(arguments[0]);
        return linhas.find(linha => linha.childElementCount > 0) || null;
        """,
        seletor_css,
    )


def navegar_aba_repasse_lanc(driver: WebDriver) -> None:
    """
    Navega até a aba repasses e lançamentos

    """
    print()

    driver.get('https://beta-portal-ec.veloe.com.br/portalec-shell-frt/repasses?aba=lancamentos')

    #Clicar em Buscar
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS
    espera = WebDriverWait(driver, timeout)
    wrapper_botao = espera.until(EC.presence_of_element_located(SELETOR_BOTAO_BUSCAR))
    _clicar_componente(driver, wrapper_botao)

    #Clicar no botão de Seta Download (Primeira vez)
    wrapper_botao = espera.until(EC.presence_of_element_located(SELETOR_BOTAO_DOWNLOAD_1))
    _clicar_componente(driver, wrapper_botao)

    #Buscar na Aba Arquivo
    driver.get('https://beta-portal-ec.veloe.com.br/portalec-shell-frt/arquivos')

    # Aguarda o relatório ficar pronto e baixa
    aguardar_status_sucesso_e_baixar(driver)

def aguardar_status_sucesso_e_baixar(
    driver: WebDriver,
    timeout: int = TIMEOUT_AGUARDAR_RELATORIO_SEGUNDOS,
    intervalo: int = INTERVALO_VERIFICACAO_SEGUNDOS,
) -> None:
    """Aguarda a primeira linha da tabela de relatórios ficar com status
    "Sucesso" e clica no ícone de download correspondente.

    A cada verificação (exceto a primeira), a página é recarregada
    (`driver.refresh()`) porque o site não atualiza o status sozinho —
    só reflete o status atual no momento do carregamento da página.
    """
    tempo_inicial = time.monotonic()
    tentativa = 0

    while True:
        tentativa += 1
        tempo_decorrido = time.monotonic() - tempo_inicial
        texto_status = ""

        if tentativa > 1:
            driver.refresh()
            # Espera ativa até a linha reaparecer no DOM pós-refresh,
            # com teto de segurança para não travar indefinidamente.
            tempo_refresh_inicial = time.monotonic()
            timeout_pos_refresh = 15
            while _buscar_primeira_linha_com_dados(driver, "tr.vlv-table-line-content") is None:
                if time.monotonic() - tempo_refresh_inicial >= timeout_pos_refresh:
                    logger.warning(
                        "Verificação %d: nenhuma linha reapareceu %ds após refresh.",
                        tentativa,
                        timeout_pos_refresh,
                    )
                    break
                time.sleep(0.5)

        primeira_linha = _buscar_primeira_linha_com_dados(driver, "tr.vlv-table-line-content")

        if primeira_linha is not None:
            try:
                celula_status = driver.execute_script(
                    """
                    const linha = arguments[0];
                    const celulas = linha.querySelectorAll('td');
                    return celulas.length > 3
                        ? celulas[3].querySelector('vlv-table-cel-content')
                        : null;
                    """,
                    primeira_linha,
                )
                if celula_status is not None:
                    texto_status = _ler_texto_shadow(driver, celula_status)
            except StaleElementReferenceException as exc:
                logger.warning(
                    "Verificação %d: linha ficou obsoleta durante leitura (%s). "
                    "Tentando novamente.",
                    tentativa,
                    exc,
                )
        else:
            logger.warning(
                "Verificação %d: nenhuma linha da tabela encontrada ainda.",
                tentativa,
            )

        logger.info(
            "Verificação %d (%.0fs decorridos): status atual = '%s'.",
            tentativa,
            tempo_decorrido,
            texto_status,
        )

        if texto_status.lower() == STATUS_SUCESSO.lower():
            logger.info(
                "Status '%s' detectado na primeira linha após %.0fs.",
                STATUS_SUCESSO,
                tempo_decorrido,
            )
            break

        if tempo_decorrido >= timeout:
            logger.error(
                "Status não mudou para '%s' após %d segundos.",
                STATUS_SUCESSO,
                timeout,
            )
            raise TimeoutException(
                f"Relatório não ficou com status '{STATUS_SUCESSO}' após "
                f"{timeout} segundos de espera (último status lido: "
                f"'{texto_status}')."
            )

        time.sleep(intervalo)

    # Relocaliza a linha do zero antes do clique — o Angular pode ter
    # re-renderizado a <tr> no momento em que o status virou "Sucesso".
    primeira_linha = _buscar_primeira_linha_com_dados(driver, "tr.vlv-table-line-content")

    if primeira_linha is None:
        raise NoSuchElementException(
            "Linha da tabela não encontrada ao tentar localizar o ícone "
            "de download, após status 'Sucesso'."
        )

    wrapper_icone = driver.execute_script(
        """
        const linha = arguments[0];
        const celulas = linha.querySelectorAll('td');
        return celulas.length > 4
            ? celulas[4].querySelector('vlv-table-cel-content vlv-button-icon')
            : null;
        """,
        primeira_linha,
    )

    if wrapper_icone is None:
        raise NoSuchElementException(
            "Ícone de download não encontrado na primeira linha após "
            "status 'Sucesso'."
        )

    _clicar_componente(driver, wrapper_icone)
    logger.info("Clique no ícone de download realizado.")
