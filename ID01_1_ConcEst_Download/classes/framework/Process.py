# O InitAllSettings precisa ser o primeiro a ser carregado
from ID01_1_ConcEst_Download.classes.framework.InitAllSettings import InitAllSettings
from ID01_1_ConcEst_Download.classes.framework.GetTransaction import GetTransaction
from ID01_1_ConcEst_Download.classes.utils.Log import Log
from ID01_1_ConcEst_Download.classes.utils.Exceptions import BusinessRuleException
from ID01_1_ConcEst_Download.classes.utils.limpar_diretorio import limpar_diretorio
from ID01_1_ConcEst_Download.classes.utils.renomear_arquivo import (
    aguardar_novos_arquivos,
    listar_arquivos,
    renomear_arquivos_novos,
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

from ID01_1_ConcEst_Download.classes.sites import cielo_email

from ID01_1_ConcEst_Download.classes.sites import bradesco_email

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


# Com None, a adquirente vem do item da fila.
ADQUIRENTE_TESTE: Optional[str] = None

# Adquirentes cujos arquivos mantêm o nome original (não renomear).
MANTER_NOME_ORIGINAL: frozenset[str] = frozenset({'CIELO'})

# Quantidade de arquivos que a Cielo deve baixar.
QTD_ARQUIVOS_CIELO: int = 5


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
    'CIELO': Adquirente(
        'Cielo', navegar=lambda driver: cielo_email.buscar_arquivos_email()
    ),
    'BRADESCO': Adquirente(
        'Bradesco', navegar=lambda driver: bradesco_email.buscar_email_bradesco()
    ),
    # 'BRADESCO': Adquirente('Bradesco'),  # TODO: login/navegação pendentes
}


class Process:
    """Processamento principal: baixa o arquivo da adquirente do item da fila."""

    @classmethod
    def execute(cls) -> None:
        """Faz login, navega e baixa o relatório da adquirente do item atual.

        Raises:
            BusinessRuleException: Se a adquirente não for suportada ou se
                a Cielo não baixar todos os arquivos esperados.
        """
        Log.write_log('Process Started')

        driver = InitAllSettings.web_driver
        info = GetTransaction.queue_item['info_adicionais']
        adquirente = ADQUIRENTE_TESTE or str(info['adquirente']).strip().upper()

        etapas = ADQUIRENTES.get(adquirente)
        if etapas is None:
            raise BusinessRuleException(f'Adquirente inválida: {adquirente}')

        pasta = InitAllSettings.config['arquivos_baixados']
        arquivos_antes = listar_arquivos(pasta)  # foto ANTES do download

        Log.write_log(f'Entrando Site {etapas.nome_log}')
        if etapas.login:
            etapas.login(driver=driver)
        if etapas.navegar:
            etapas.navegar(driver=driver)

        if adquirente in MANTER_NOME_ORIGINAL:
            cls._validar_arquivos_originais(
                pasta=pasta,
                arquivos_antes=arquivos_antes,
                quantidade_esperada=QTD_ARQUIVOS_CIELO,
            )
            Log.write_log(f'{etapas.nome_log}: nome original mantido')
        else:
            renomear_arquivos_novos(
                pasta=pasta,
                novo_nome_base=adquirente,
                arquivos_antes=arquivos_antes,
            )

        Log.write_log('Process Finished')

    @staticmethod
    def _validar_arquivos_originais(
        pasta: str | Path,
        arquivos_antes: dict[Path, int],
        quantidade_esperada: int,
    ) -> None:
        """Confirma que todos os arquivos esperados foram baixados.

        Se a quantidade baixada for diferente da esperada, limpa a pasta
        de arquivos baixados para que a próxima execução comece do zero.

        Args:
            pasta: pasta de download.
            arquivos_antes: foto da pasta tirada antes do download.
            quantidade_esperada: quantidade exata de arquivos novos.

        Raises:
            BusinessRuleException: se a quantidade baixada for diferente
                da esperada.
        """
        mensagem = f'Não foram baixados os {quantidade_esperada} arquivos'
        pasta_baixados = Path(InitAllSettings.config['arquivos_baixados'])
        try:
            novos = aguardar_novos_arquivos(
                pasta=pasta,
                arquivos_antes=arquivos_antes,
                quantidade_esperada=quantidade_esperada,
            )
        except TimeoutError as erro:
            limpar_diretorio(pasta_baixados)
            raise BusinessRuleException(mensagem) from erro

        if len(novos) != quantidade_esperada:
            limpar_diretorio(pasta_baixados)
            raise BusinessRuleException(mensagem)