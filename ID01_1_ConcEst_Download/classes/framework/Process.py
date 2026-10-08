# O InitAllSettings precisa ser o primeiro a ser carregado
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings
from ID01_1_ConcEst_Download.classes.framework.GetTransaction import GetTransaction
from ID01_1_ConcEst_Download.classes.utils.Log import Log
from ID01_1_ConcEst_Download.classes.utils.Exceptions import BusinessRuleException
from ID01_1_ConcEst_Download.classes.utils.renomear_arquivo import (
    renomear_arquivo_mais_recente,
)
from ID01_1_ConcEst_Download.classes.sites.veloe import (
    fazer_login_veloe,
    navegar_aba_repasse_lanc,
)
from ID01_1_ConcEst_Download.classes.sites.semparar import (
    fazer_login_semparar,
    navegar_aba_transacoes_semparar,
)
from ID01_1_ConcEst_Download.classes.sites.greenpass import (
    fazer_login_greenpass,
    navegar_aba_estadia_taggy,
)
from ID01_1_ConcEst_Download.classes.sites.conectcar import (
    fazer_login_conectcar,
    navegar_aba_transacoes,
)
from ID01_1_ConcEst_Download.classes.sites.cielo import (
    fazer_login_cielo,
    navegar_aba_cielo,
)

from dataclasses import dataclass
from typing import Callable, Optional

# TODO: remover antes de ir para produção (usado apenas em testes).
# Com None, a adquirente vem do item da fila.
ADQUIRENTE_TESTE: Optional[str] = None


@dataclass(frozen=True)
class Adquirente:
    """Etapas de download de uma adquirente.

    Attributes:
        nome_log: Nome exibido nos logs.
        login: Função que faz login no site (None se não se aplica).
        navegar: Função que navega até o relatório e baixa o arquivo.
    """

    nome_log: str
    login: Optional[Callable[..., None]] = None
    navegar: Optional[Callable[..., None]] = None


ADQUIRENTES: dict[str, Adquirente] = {
    'VELOE': Adquirente('Veloe', fazer_login_veloe, navegar_aba_repasse_lanc),
    'GREENPASS': Adquirente(
        'GreenPass', fazer_login_greenpass, navegar_aba_estadia_taggy
    ),
    'SEM PARAR': Adquirente(
        'Sem Parar', fazer_login_semparar, navegar_aba_transacoes_semparar
    ),
    'CONECTCAR': Adquirente(
        'Conectcar', fazer_login_conectcar, navegar_aba_transacoes
    ),
    # 'CIELO': Adquirente('Cielo', fazer_login_cielo, navegar_aba_cielo),
    # 'BRADESCO': Adquirente('Bradesco'),  # TODO: login/navegação pendentes
}


class Process:
    """Processamento principal: baixa o arquivo da adquirente do item da fila."""

    @classmethod
    def execute(cls) -> None:
        """Faz login, navega e baixa o relatório da adquirente do item atual.

        Raises:
            BusinessRuleException: Se a adquirente não for suportada.
        """
        Log.write_log('Process Started')

        driver = InitAllSettings.web_driver
        info = GetTransaction.queue_item['info_adicionais']
        adquirente = ADQUIRENTE_TESTE or str(info['adquirente']).strip().upper()

        etapas = ADQUIRENTES.get(adquirente)
        if etapas is None:
            raise BusinessRuleException(f'Adquirente inválida: {adquirente}')

        Log.write_log(f'Entrando Site {etapas.nome_log}')
        if etapas.login:
            etapas.login(driver=driver)
        if etapas.navegar:
            etapas.navegar(driver=driver)

        renomear_arquivo_mais_recente(
            pasta=InitAllSettings.config['arquivos_baixados'],
            novo_nome_base=adquirente,
        )

        Log.write_log('Process Finished')