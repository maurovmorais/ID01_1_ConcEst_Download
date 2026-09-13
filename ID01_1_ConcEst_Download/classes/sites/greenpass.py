"""Função de login no Portal Estabelecimentos Comerciais (GreenPass).

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
from ID01_1_ConcEst_Download.classes.utils.util_data import obter_intervalo_ontem

logger = logging.getLogger(__name__)

URL_LOGIN = ('https://conveniado.greenpass.com.br/Account/Login')
NOME_CREDENCIAL_WINDOWS = "site_greenpass"

USUARIO = InitAllSettings.config['usuarios']

SELETOR_CAMPO_EMAIL = (By.XPATH,'//*[@id="Email"]')

#Tempos e dalays
TIMEOUT_PADRAO_SEGUNDOS = 20
TENTATIVAS_MAXIMAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 3

def fazer_login_greenpass(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS,
    tentativas_maximas: int = TENTATIVAS_MAXIMAS,
) -> None:
    """Realiza o login no Portal Estabelecimentos Comerciais (GreenPass).

    Usuário e senha são recuperados do Gerenciador de Credenciais do
    Windows (credencial "site_GreenPass)"). Utiliza a instância de Chrome já
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
                "Tentativa %d/%d de login no Portal GreenPass.",
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
            email_usuario = driver.find_element(By.XPATH,'//*[@id="Email"]')
            email_usuario.send_keys(USUARIO)
            
            # Preencher a senha
            senha_usuario = driver.find_element(By.XPATH,'//*[@id="Password"]')
            senha_usuario.send_keys(senha)

            # Clicar em entrar
            botao_entrar = driver.find_element(By.XPATH,'//*[@id="btnConfirm"]')
            botao_entrar.click()


            # Confirma que o login foi bem-sucedido aguardando a URL sair
            # da tela de login (ajustar condição conforme comportamento
            # real do site, ex.: aguardar um elemento exclusivo do home).
            espera.until(lambda d: "login" not in d.current_url.lower())

            logger.info("Login no Portal GreenPass realizado com sucesso.")
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




def navegar_aba_estadia_taggy(driver: WebDriver) -> None:
    """
    Navega até a aba Estadia do Taggy

    """
    try:
        #Navega para a Tela
        driver.get('https://conveniado.greenpass.com.br/TaggyStayHistory')

        #Preenche campo data
        cammpo_data = driver.find_element(By.XPATH,'//*[@id="StayPeriod"]')

        #Chama a função para obter o texto
        texto_para_campo = obter_intervalo_ontem()
        cammpo_data.send_keys(texto_para_campo)
        
        #Faz o filtro
        botao_filtro = driver.find_element(By.XPATH,'//*[@id="valid-form"]')
        time.sleep(3)
        botao_filtro.click()
        time.sleep(1)

        #Faz o download
        botao_download = driver.find_element(By.XPATH,'/html/body/div[3]/div/main/div/div[3]/div[3]/div/div/div[1]/div[1]/div[2]/div/button')
        time.sleep(1)
        botao_download.click()
        time.sleep(1)
        botao_opcao_xlsx = driver.find_element(By.XPATH,'/html/body/div[3]/div/main/div/div[3]/div[3]/div/div/div[1]/div[1]/div[2]/div/ul/li[1]/a')
        time.sleep(1)
        botao_opcao_xlsx.click()
        time.sleep(3)
        
    except Exception as err:
        Log.write_log(f"Falha no Download - Erro: {err}")
        raise

    