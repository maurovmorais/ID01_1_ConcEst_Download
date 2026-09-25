"""Função de login no Portal Estabelecimentos Comerciais (Sem Parar).

Reutiliza a instância do Chrome/WebDriver já iniciada pela automação
(o driver deve ser criado e passado por quem chama esta função —
nenhuma nova janela de navegador é aberta aqui).
"""

import logging
import time
from datetime import date, timedelta, datetime
import re
from pathlib import Path
import sqlite3

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
from ID01_1_ConcEst_Download.classes.excel.gerar_relat_semparar import exportar_tbl_cred_semparar_para_excel

logger = logging.getLogger(__name__)


URL_LOGIN = ('https://credenciados.semparar.com.br/login')
NOME_CREDENCIAL_WINDOWS = "site_semparar"
USUARIO = InitAllSettings.config['usuarios']
SELETOR_CAMPO_EMAIL = (By.XPATH,'//*[@id="mat-input-0"]')
XPATH_BOTAO_ENTRAR = ("//button[@type='submit' and .//span[normalize-space(text())='Entrar']]")
XPATH_BOTAO_PERIODO = "//button[contains(@class, 'mat-calendar-period-button')]"
XPATH_BOTAO_PROXIMO_MES = "//button[contains(@class, 'mat-calendar-next-button')]"
XPATH_BOTAO_MES_ANTERIOR = "//button[contains(@class, 'mat-calendar-previous-button')]"
CAMINHO_BANCO_DADOS = Path(InitAllSettings.config['CaminhoBancoSqlite'])
XPATH_CAMPO_CREDENCIADOS = ("//mat-form-field[.//mat-label[contains(text(), 'Credenciados')]]//mat-select")
XPATH_PAINEL_ABERTO = "//div[@role='listbox' and contains(@class, 'mat-mdc-select-panel')]"
XPATH_OPCOES_NO_PAINEL = f"{XPATH_PAINEL_ABERTO}//mat-option"
SELETOR_TEXTO_OPCAO = "span.mdc-list-item__primary-text"
XPATH_BOTAO_FILTRAR = "//button[.//span[normalize-space(text())='Filtrar']]"
XPATH_VALOR_TOTAL = '/html/body/app-root/app-layout/mat-sidenav-container/mat-sidenav-content/main/div/mat-drawer-container/mat-drawer-content/ng-component/div/ng-component/div/div[3]/div[6]/div[2]'

#Tempos e dalays
TIMEOUT_PADRAO_SEGUNDOS = 20
TENTATIVAS_MAXIMAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 3
TIMEOUT_PADRAO = 30
TEMPO_ESPERA_ESTABILIZACAO = 3.0  # segundos entre leituras
TENTATIVAS_MAXIMAS_ESTABILIZACAO = 5
TIMEOUT_REQUISICAO = 15
LEITURAS_ESTAVEIS_NECESSARIAS = 3  # 3 leituras seguidas iguais = estável


MESES_EM_INGLES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

def fazer_login_semparar(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS,
    tentativas_maximas: int = TENTATIVAS_MAXIMAS,
) -> None:
    """Realiza o login no Portal Estabelecimentos Comerciais (Sem Parar).

    Usuário e senha são recuperados do Gerenciador de Credenciais do
    Windows (credencial "site_SemParar)"). Utiliza a instância de Chrome já
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
                "Tentativa %d/%d de login no Portal SemParar.",
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
            email_usuario = driver.find_element(By.XPATH,'//*[@id="mat-input-0"]')
            email_usuario.send_keys(USUARIO)
            
            # Preencher a senha
            senha_usuario = driver.find_element(By.XPATH,'//*[@id="mat-input-1"]')
            senha_usuario.send_keys(senha)

            print("Inserir capctha manualmente")

            # Clicar em entrar
            clicar_botao_entrar(driver)

            # Confirma que o login foi bem-sucedido aguardando a URL sair
            # da tela de login (ajustar condição conforme comportamento
            # real do site, ex.: aguardar um elemento exclusivo do home).
            espera.until(lambda d: "login" not in d.current_url.lower())

            logger.info("Login no Portal SemParar realizado com sucesso.")
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


def clicar_botao_entrar(driver: WebDriver, timeout: int = TIMEOUT_PADRAO) -> None:
    """Clica no botão 'Entrar' do login, aguardando ele ficar habilitado.

    O botão possui o atributo `disabled` até o formulário (e-mail,
    senha e reCAPTCHA) ficar válido, então a espera considera tanto
    a clicabilidade quanto a ausência do atributo `disabled`.

    Args:
        driver: instância do WebDriver já posicionada na tela de
            login (credenciados.semparar.com.br), com e-mail, senha
            e reCAPTCHA já preenchidos.
        timeout: tempo máximo (em segundos) de espera pelo botão
            ficar habilitado e clicável.

    Raises:
        TimeoutException: se o botão não ficar habilitado/clicável
            dentro do tempo definido (ex.: reCAPTCHA não resolvido).
    """
    try:
        botao_entrar = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_ENTRAR))
        )
        botao_entrar.click()
        logger.info("Botão 'Entrar' clicado com sucesso.")
    except TimeoutException:
        logger.error(
            "Botão 'Entrar' não ficou habilitado/clicável em %s "
            "segundos (verifique se o reCAPTCHA foi resolvido).",
            timeout,
        )
        raise




def navegar_aba_transacoes_semparar(driver: WebDriver) -> None:
    """
    Navega até a aba Estadia do Taggy

    """
    try:
        #Navega para a Tela
        driver.get('https://credenciados.semparar.com.br/transactions')

        #Chama a função para obter o texto
        data_str = obter_data_ontem()
        
        #Expandir Calendario
        time.sleep(3)
        expandir_calendario = driver.find_element(By.XPATH,'/html/body/app-root/app-layout/mat-sidenav-container/mat-sidenav-content/main/div/mat-drawer-container/mat-drawer-content/ng-component/div/ng-component/div/form/div[1]/div[1]/div/div[2]/div[1]/mat-form-field/div[1]/div/div[3]/mat-datepicker-toggle/button/span[3]')
        expandir_calendario.click()

        #Preenche campo data
        preencher_periodo_personalizado(driver,datetime.strptime(data_str, "%d/%m/%Y").date(),datetime.strptime(data_str, "%d/%m/%Y").date())

        #Informar o Grupo
        campo_grupo = driver.find_element(By.XPATH,'/html/body/app-root/app-layout/mat-sidenav-container/mat-sidenav-content/main/div/mat-drawer-container/mat-drawer-content/ng-component/div/ng-component/div/form/div[1]/div[3]/div/div[2]/div[1]/div[1]/auto-complete/mat-form-field/div[1]/div/div[2]/mat-select/div')
        campo_grupo.click()
        time.sleep(1)
        botao_todos_crend = driver.find_element(By.XPATH,'/html/body/div[4]/div[2]/div/div/mat-option[1]/span')
        botao_todos_crend.click()

        #Pegar Valor total para cada credenciado
        expandir_campo_credenciado = driver.find_element(By.XPATH,'/html/body/app-root/app-layout/mat-sidenav-container/mat-sidenav-content/main/div/mat-drawer-container/mat-drawer-content/ng-component/div/ng-component/div/form/div[1]/div[3]/div/div[2]/div[1]/div[2]/auto-complete/mat-form-field/div[1]/div/div[2]/mat-select/div')
        expandir_campo_credenciado.click()

        #Processar todos Crendenciados
        processar_todos_credenciados(driver, datetime.strptime(data_str, "%d/%m/%Y").date(),datetime.strptime(data_str, "%d/%m/%Y").date())

        #Salvar Arquivo de Excel
        caminho_banco = CAMINHO_BANCO_DADOS
        diretorio_destino = Path(InitAllSettings.config['arquivos_baixados'])
        caminho_gerado = exportar_tbl_cred_semparar_para_excel(caminho_banco, diretorio_destino)

        print()
        
    except Exception as err:
        Log.write_log(f"Falha no Download - Erro: {err}")
        raise

    
def _formatar_aria_label(data_alvo: date) -> str:
    """Monta o aria-label no mesmo formato usado pelo Angular Material
    (ex.: 'September 14, 2026'), independente do idioma da tela."""
    nome_mes = MESES_EM_INGLES[data_alvo.month - 1]
    return f"{nome_mes} {data_alvo.day}, {data_alvo.year}"


def _mes_ano_atual_calendario(driver: WebDriver) -> tuple[int, int]:
    """Lê o cabeçalho do calendário (ex.: 'SEP 2026') e retorna (mes, ano)."""
    texto_cabecalho = driver.find_element(
        By.XPATH, XPATH_BOTAO_PERIODO
    ).text.strip()
    abreviacao_mes, ano = texto_cabecalho.split()
    mes = next(
        indice + 1
        for indice, nome in enumerate(MESES_EM_INGLES)
        if nome.upper().startswith(abreviacao_mes.upper())
    )
    return mes, int(ano)


def navegar_para_mes(driver: WebDriver, data_alvo: date, timeout: int = TIMEOUT_PADRAO) -> None:
    """Navega o calendário (setas < >) até o mês/ano de data_alvo."""
    for _ in range(24):  # limite de segurança (2 anos de navegação)
        mes_atual, ano_atual = _mes_ano_atual_calendario(driver)
        if (mes_atual, ano_atual) == (data_alvo.month, data_alvo.year):
            return

        xpath_seta = (
            XPATH_BOTAO_PROXIMO_MES
            if (ano_atual, mes_atual) < (data_alvo.year, data_alvo.month)
            else XPATH_BOTAO_MES_ANTERIOR
        )
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_seta))
        ).click()

    logger.error("Não foi possível navegar até %s/%s no calendário.", data_alvo.month, data_alvo.year)
    raise TimeoutException("Falha ao navegar até o mês/ano desejado no calendário.")


def selecionar_data_no_calendario(driver: WebDriver, data_alvo: date, timeout: int = TIMEOUT_PADRAO) -> None:
    """Navega até o mês certo e clica no dia correspondente a data_alvo."""
    navegar_para_mes(driver, data_alvo, timeout)

    aria_label = _formatar_aria_label(data_alvo)
    xpath_dia = f"//button[contains(@class, 'mat-calendar-body-cell') and @aria-label='{aria_label}']"

    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_dia))
        ).click()
        logger.info("Data selecionada no calendário: %s", data_alvo.strftime("%d/%m/%Y"))
    except TimeoutException:
        logger.error("Não foi possível clicar na data %s no calendário.", data_alvo.strftime("%d/%m/%Y"))
        raise


def preencher_periodo_personalizado(
    driver: WebDriver,
    data_inicial: date,
    data_final: date,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Preenche o período personalizado clicando na data inicial e final
    do calendário (o próprio Angular Material fecha o range ao clicar
    nas duas datas em sequência).

    Args:
        driver: WebDriver com o calendário já aberto na tela.
        data_inicial: data inicial do período.
        data_final: data final do período.
        timeout: tempo máximo de espera por elemento, em segundos.
    """
    selecionar_data_no_calendario(driver, data_inicial, timeout)
    if data_final != data_inicial:
        selecionar_data_no_calendario(driver, data_final, timeout)
    else:
        # Mesmo dia para início e fim (ex.: 14/09/2026 - 14/09/2026):
        # o Material Datepicker de range exige um segundo clique na
        # mesma célula para fechar o range no mesmo dia.
        selecionar_data_no_calendario(driver, data_final, timeout)



def abrir_dropdown_credenciados(driver: WebDriver, timeout: int = TIMEOUT_PADRAO) -> None:
    """Abre o dropdown 'Credenciados' e aguarda o painel de opções abrir."""
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, XPATH_CAMPO_CREDENCIADOS))
    ).send_keys(Keys.ENTER)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, XPATH_PAINEL_ABERTO))
    )


def listar_credenciados(driver: WebDriver, timeout: int = TIMEOUT_PADRAO) -> list[str]:
    """Retorna o texto de cada credenciado (ex.: '603 - SHOPPING POCOS
    DE CALDAS') presente no painel de opções já aberto."""
    WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.XPATH, XPATH_OPCOES_NO_PAINEL))
    )
    opcoes = driver.find_elements(By.XPATH, XPATH_OPCOES_NO_PAINEL)
    return [
        opcao.find_element(By.CSS_SELECTOR, SELETOR_TEXTO_OPCAO).text.strip()
        for opcao in opcoes
    ]


def _opcao_esta_marcada(opcao: WebElement) -> bool:
    """Verifica se um <mat-option> está marcado, via aria-selected."""
    return opcao.get_attribute("aria-selected") == "true"


def selecionar_apenas_credenciado(
    driver: WebDriver, texto_credenciado: str, timeout: int = TIMEOUT_PADRAO
) -> None:
    """No painel já aberto, desmarca qualquer credenciado marcado e
    marca apenas o informado (busca por correspondência exata de
    texto, ex.: '603 - SHOPPING POCOS DE CALDAS')."""
    opcoes = driver.find_elements(By.XPATH, XPATH_OPCOES_NO_PAINEL)

    opcao_alvo = None
    for opcao in opcoes:
        texto_opcao = opcao.find_element(By.CSS_SELECTOR, SELETOR_TEXTO_OPCAO).text.strip()
        marcada = _opcao_esta_marcada(opcao)

        if texto_opcao == texto_credenciado:
            opcao_alvo = opcao
            if not marcada:
                opcao.click()
        elif marcada:
            opcao.click()

    if opcao_alvo is None:
        logger.error("Credenciado não encontrado na lista: %s", texto_credenciado)
        raise ValueError(f"Credenciado não encontrado na lista: {texto_credenciado}")

    logger.info("Credenciado selecionado: %s", texto_credenciado)


def clicar_filtrar(driver: WebDriver, timeout: int = TIMEOUT_PADRAO) -> None:
    """Clica no botão 'Filtrar'."""
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_FILTRAR))
    ).send_keys(Keys.ENTER)


def _ler_texto_valor_total(driver: WebDriver) -> str:
    """Lê o texto bruto atual do card 'Valor total' (div.amount)."""
    elemento = driver.find_element(By.XPATH, XPATH_VALOR_TOTAL)
    return elemento.text.strip()


def _botao_filtrar_esta_desabilitado(driver: WebDriver) -> bool:
    """Verifica se o botão 'Filtrar' está desabilitado (indicando
    requisição em andamento)."""
    botao = driver.find_element(By.XPATH, XPATH_BOTAO_FILTRAR)
    return botao.get_attribute("disabled") is not None


def aguardar_valor_total_carregar(
    driver: WebDriver,
    timeout_requisicao: int = TIMEOUT_REQUISICAO,
    timeout_estabilizacao: int = TIMEOUT_PADRAO,
) -> str:
    """Aguarda o card 'Valor total' atualizar após o clique em
    'Filtrar'.

    Estratégia em duas fases:
    1. Aguarda o botão 'Filtrar' ficar desabilitado e depois
       habilitado novamente — isso captura o ciclo real da
       requisição (loading), evitando ler o valor antigo antes da
       requisição sequer começar.
    2. Depois disso, ainda exige várias leituras consecutivas
       idênticas do valor, como garantia extra contra qualquer
       repaint intermediário do Angular.

    Args:
        driver: WebDriver com a tela já filtrada.
        timeout_requisicao: tempo máximo de espera pelo ciclo
            desabilitado -> habilitado do botão 'Filtrar'.
        timeout_estabilizacao: tempo máximo de espera pela
            estabilização final do texto do valor.

    Returns:
        Texto final e estável do card 'Valor total'.
    """
    try:
        WebDriverWait(driver, timeout_requisicao).until(
            _botao_filtrar_esta_desabilitado
        )
        WebDriverWait(driver, timeout_requisicao).until_not(
            _botao_filtrar_esta_desabilitado
        )
    except TimeoutException:
        logger.warning(
            "Não foi possível detectar o ciclo de desabilitação do "
            "botão 'Filtrar' (pode não existir esse comportamento); "
            "seguindo direto para a checagem de estabilidade do valor."
        )

    leituras_iguais_seguidas = 0
    texto_anterior = None
    tempo_limite = time.monotonic() + timeout_estabilizacao

    while time.monotonic() < tempo_limite:
        texto_atual = _ler_texto_valor_total(driver)
        if texto_atual == texto_anterior:
            leituras_iguais_seguidas += 1
            if leituras_iguais_seguidas >= LEITURAS_ESTAVEIS_NECESSARIAS:
                return texto_atual
        else:
            leituras_iguais_seguidas = 0
            texto_anterior = texto_atual
        time.sleep(TEMPO_ESPERA_ESTABILIZACAO)

    logger.warning(
        "Valor total não estabilizou em %s segundos; usando última "
        "leitura: %s",
        timeout_estabilizacao,
        texto_anterior,
    )
    return texto_anterior


def extrair_valor_total(driver: WebDriver, timeout: int = TIMEOUT_PADRAO) -> float:
    """Lê o card 'Valor total' (div.amount, ex.: 'R$ 0,00') já
    estabilizado e converte para float."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.XPATH, XPATH_VALOR_TOTAL))
        )
    except TimeoutException:
        logger.error("Card 'Valor total' (div.amount) não encontrado na tela.")
        raise

    texto_valor = _ler_texto_valor_total(driver)
    numero = re.sub(r"[^\d,]", "", texto_valor).replace(",", ".")
    return float(numero)


def gravar_valor_credenciado(
    credenciado: str,
    valor_total: float,
    data_inicial: date,
    data_final: date,
    caminho_banco: Path = CAMINHO_BANCO_DADOS,
) -> None:
    """Grava o valor filtrado de um credenciado na tabela
    tbl_cred_semparar."""
    data_periodo = f"{data_inicial.strftime('%d/%m/%Y')} - {data_final.strftime('%d/%m/%Y')}"
    ultima_atualizacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conexao = sqlite3.connect(caminho_banco)
    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO tbl_cred_semparar
                (credenciado, valor_total, data_periodo, ultima_atualizacao)
            VALUES (?, ?, ?, ?)
            """,
            (credenciado, valor_total, data_periodo, ultima_atualizacao),
        )
        conexao.commit()
        logger.info(
            "Valor gravado: %s -> R$ %.2f (%s)",
            credenciado, valor_total, data_periodo,
        )
    finally:
        conexao.close()


def processar_todos_credenciados(
    driver: WebDriver, data_inicial: date, data_final: date
) -> None:
    """Fluxo completo: para cada credenciado, marca só ele, filtra,
    aguarda o valor carregar, extrai e grava no banco.

    Reabre o dropdown a cada iteração, pois selecionar um novo
    credenciado normalmente fecha o painel ao clicar em 'Filtrar'.
    """
    abrir_dropdown_credenciados(driver)
    credenciados = listar_credenciados(driver)
    logger.info("Total de credenciados encontrados: %s", len(credenciados))

    for credenciado in credenciados:
        abrir_dropdown_credenciados(driver)
        selecionar_apenas_credenciado(driver, credenciado)

        clicar_filtrar(driver)
        aguardar_valor_total_carregar(driver)

        valor_total = extrair_valor_total(driver)
        valor_total = str(valor_total).replace(".",",")
        gravar_valor_credenciado(credenciado, valor_total, data_inicial, data_final)