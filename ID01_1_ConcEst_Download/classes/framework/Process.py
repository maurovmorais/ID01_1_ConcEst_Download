# Imports dos módulos internos do projeto
# Carrega o InitAllSettingssSettings Precisa ser o primeiro a ser carregado
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings
from ID01_1_ConcEst_Download.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_1_ConcEst_Download.classes.utils.Exceptions import BusinessRuleException
from ID01_1_ConcEst_Download.classes.framework.GetTransaction import GetTransaction
#FIXME Código Exemplo REMOVER
from ID01_1_ConcEst_Download.classes.chrome.google.Homepage import GoogleHomepage
from ID01_1_ConcEst_Download.classes.sites.veloe import fazer_login_veloe,navegar_aba_repasse_lanc
from ID01_1_ConcEst_Download.classes.sites.semparar import fazer_login_semparar,navegar_aba_transacoes_semparar
from ID01_1_ConcEst_Download.classes.sites.greenpass import fazer_login_greenpass,navegar_aba_estadia_taggy
from ID01_1_ConcEst_Download.classes.sites.conectcar import fazer_login_conectcar,navegar_aba_transacoes
from ID01_1_ConcEst_Download.classes.utils.renomear_arquivo import renomear_arquivo_mais_recente

# Imports dos pacotes externos
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# Classe responsável pelo processamento principal, necessário preencher com o seu código no método execute
class Process:
    """
    Classe responsável pelo processamento principal.

    Parâmetros:
    
    Retorna:
    """
    _config = InitAllSettings.config
    
    
    #Parte principal do código, deve ser preenchida pelo desenvolvedor
    #Acesse o item a ser processado pelo queue_item
    @classmethod
    def execute(cls):
        """
        Método principal para execução do código.


        Parâmetros:


        Retorna:
        """
        cls.web_driver = InitAllSettings.web_driver

        Log.write_log('Process Started')
        #Informa valor no campo de pesquisa
        adquirente = GetTransaction.queue_item['info_adicionais']['adquirente']
        sleep(5)

        #Entra em cada site para fazer download de arquivos
        match adquirente:
            case 'VELOE':
                Log.write_log('Entrando Site Veloe')
                fazer_login_veloe(driver=cls.web_driver)
                navegar_aba_repasse_lanc(driver=cls.web_driver)
                #Renomear Arquivo
                renomear_arquivo_mais_recente(pasta=InitAllSettings.config['arquivos_baixados'],novo_nome_base=adquirente)
                pass
                
            case 'GREENPASS':
                Log.write_log('Entrando Site GreenPass')
                fazer_login_greenpass(driver=cls.web_driver)
                navegar_aba_estadia_taggy(driver=cls.web_driver)
                #Renomear Arquivo
                renomear_arquivo_mais_recente(pasta=InitAllSettings.config['arquivos_baixados'],novo_nome_base=adquirente)
                pass
            
            case 'SEM PARAR':
                Log.write_log('Entrando Site Sem Parar')
                fazer_login_semparar(driver=cls.web_driver)
                navegar_aba_transacoes_semparar(driver=cls.web_driver)
                #Renomear Arquivo
                renomear_arquivo_mais_recente(pasta=InitAllSettings.config['arquivos_baixados'],novo_nome_base=adquirente)
                pass

            case 'CONECTCAR':
                Log.write_log('Entrando Site Conectcar')
                fazer_login_conectcar(driver=cls.web_driver)
                navegar_aba_transacoes(driver=cls.web_driver)
                #Renomear Arquivo
                renomear_arquivo_mais_recente(pasta=InitAllSettings.config['arquivos_baixados'],novo_nome_base=adquirente)
                pass

            case 'BRADESCO':
                Log.write_log('Entrando Site Bradesco')
                pass

            case 'CIELO':
                Log.write_log('Lendo Email')
                pass

            case _:
                Log.write_log("Opção inválida!") # Funciona como o 'default'

        Log.write_log('Process Finished')