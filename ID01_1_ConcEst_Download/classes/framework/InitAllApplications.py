# Imports dos módulos internos do projeto
# Carrega o InitAllSettingsSettings Precisa ser o primeiro a ser carregado
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings
from ID01_1_ConcEst_Download.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_1_ConcEst_Download.classes.utils.Exceptions import BusinessRuleException
from ID01_1_ConcEst_Download.classes.queue.QueueManager import QueueManager
import ID01_1_ConcEst_Download.classes.utils.GenericReusable as GenericReusable
from ID01_1_ConcEst_Download.classes.utils.limpar_diretorio import limpar_diretorio
from pathlib import Path

from ID01_1_ConcEst_Download.classes.chrome.google.Homepage import GoogleHomepage
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import Browser

class InitAllApplications:
    """
    Classe feita para Iniciar as aplicações de inicio de processo e também preencher a fila caso seja um processo simples para capturar
    itens que vão para a fila.
        
    Parâmetros:

    Retorna:
    """
    _config:dict = InitAllSettings.config


    @classmethod
    def add_to_queue(cls):
        """
        Adiciona itens à fila no início do processo, se necessário.

        Observação:
        - Código placeholder.
        - Se o seu projeto precisa de mais do que um método simples para subir a sua fila, considere fazer um projeto dispatcher.

        Parâmetros:
        """
        #Limpa fila remanescente
        QueueManager.abandon_queue()

        #Limpar Tabela tbl_cred_semparar
        QueueManager.delete_tbl_cred_semparar()

        #Limpar pasta download
        limpar_diretorio(Path(InitAllSettings.config['arquivos_baixados']))

        #Lista dos adquirentes
        adquirente_lista = ['CIELO','SEM PARAR','VELOE','GREENPASS','CONECTCAR','BRADESCO']

        for adquirente in adquirente_lista:
            referencia_adq = adquirente
            info_adicional = {'adquirente': adquirente}

            QueueManager.insert_new_queue_item(referencia=str(referencia_adq),inf_adicional=info_adicional)

        Log.write_log('Fila inserida com sucesso')
        
    @classmethod
    def execute(cls, first_run=False):
        """
        Executa a inicialização dos aplicativos necessários.

        
        Parâmetros:
        - first_run (bool): indica se é a primeira execução (default=False).
        
        Observação:
        - Edite o valor da variável `max_tentativas` no arquivo Config.xlsx.
        
        Retorna:
        """
      

        Log.write_log("InitAllApplications Started")

        #Chama o método para subir a fila, apenas se for a primeira vez
        if(first_run):
            cls.add_to_queue()

        #Edite o valor dessa variável a no arquivo Config.xlsx
        max_tentativas = cls._config["MaxRetryNumber"]
        
        for tentativa in range(max_tentativas):
            try:
                Log.write_log("Iniciando aplicativos, tentativa " + (tentativa+1).__str__())
 
                InitAllSettings.initiate_web_manipulator(headless=False, browser_escolhido=Browser.CHROME,pasta_download=InitAllSettings.config['arquivos_baixados'])
                
            except BusinessRuleException as err:
                raise err
            except Exception as err:
                Log.write_log(GenericReusable.get_computer_usage())
                Log.write_log(mensagem_log="Erro, tentativa " + (tentativa+1).__str__() + ": " + str(err), log_level=LogLevel.ERROR, error_type=ErrorType.APP_ERROR)

                if(tentativa+1 == max_tentativas): 
                    raise err
                else: 
                    # Inclua aqui o código responsável para reiniciar ao estado indicado para iniciar as aplicações novamente
                    continue
            else:
                Log.write_log("InitAllApplications Finished")
                break
            
