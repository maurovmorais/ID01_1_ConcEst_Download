import logging
from pathlib import Path
from time import monotonic, sleep

logger = logging.getLogger(__name__)

EXTENSOES_TEMPORARIAS = {'.crdownload', '.part', '.tmp', '.download'}


def listar_arquivos(pasta: str | Path) -> dict[Path, int]:
    """Tira uma foto dos arquivos da pasta.

    Args:
        pasta: pasta a ser inspecionada.

    Returns:
        Dicionário {caminho: data de modificação em ns}.

    Raises:
        NotADirectoryError: se pasta não for uma pasta.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        logger.error('Caminho informado não é uma pasta: %s', pasta)
        raise NotADirectoryError(
            f'Caminho informado não é uma pasta: {pasta}'
        )
    return {
        item: item.stat().st_mtime_ns
        for item in pasta.iterdir()
        if item.is_file()
    }


def _arquivos_novos(
    pasta: Path, antes: dict[Path, int]
) -> dict[Path, int]:
    """Arquivos que não existiam (ou foram modificados) desde a foto."""
    agora = listar_arquivos(pasta)
    return {
        caminho: mtime
        for caminho, mtime in agora.items()
        if antes.get(caminho) != mtime
    }


def aguardar_novos_arquivos(
    pasta: str | Path,
    arquivos_antes: dict[Path, int],
    quantidade_esperada: int = 1,
    timeout: float = 60.0,
    intervalo: float = 1.0,
    segundos_estavel: float = 3.0,
) -> list[Path]:
    """Espera os downloads terminarem e devolve os arquivos novos.

    Considera finalizado quando não há arquivo temporário, existem ao
    menos `quantidade_esperada` arquivos novos e nada mudou por
    `segundos_estavel` segundos.

    Args:
        pasta: pasta de download.
        arquivos_antes: foto da pasta tirada antes do download.
        quantidade_esperada: mínimo de arquivos novos esperados.
        timeout: tempo máximo de espera, em segundos.
        intervalo: intervalo entre verificações, em segundos.
        segundos_estavel: tempo sem mudanças para considerar concluído.

    Returns:
        Lista ordenada com os caminhos dos arquivos novos.

    Raises:
        TimeoutError: se os downloads não terminarem no prazo.
    """
    pasta = Path(pasta)
    limite = monotonic() + timeout
    ultimo_estado: dict[Path, tuple[int, int]] | None = None
    estavel_desde = monotonic()

    while monotonic() < limite:
        novos = _arquivos_novos(pasta, arquivos_antes)

        # tamanho + mtime: qualquer mudança reinicia a contagem
        estado: dict[Path, tuple[int, int]] = {}
        for caminho, mtime in novos.items():
            if caminho.exists():
                estado[caminho] = (caminho.stat().st_size, mtime)

        temporarios = [
            c for c in estado if c.suffix.lower() in EXTENSOES_TEMPORARIAS
        ]
        prontos = sorted(c for c in estado if c not in temporarios)

        if estado != ultimo_estado:
            ultimo_estado = estado
            estavel_desde = monotonic()
        elif (
            not temporarios
            and len(prontos) >= quantidade_esperada
            and monotonic() - estavel_desde >= segundos_estavel
        ):
            return prontos
        sleep(intervalo)

    logger.error('Timeout aguardando download em: %s', pasta)
    raise TimeoutError(f'Download não finalizou em {timeout}s: {pasta}')


def renomear_arquivos_novos(
    pasta: str | Path,
    novo_nome_base: str,
    arquivos_antes: dict[Path, int],
    quantidade_esperada: int = 1,
    timeout: float = 60.0,
) -> list[Path]:
    """Renomeia SOMENTE os arquivos baixados após a foto da pasta.

    Um arquivo vira `<base><ext>`; vários viram `<base>_1<ext>`,
    `<base>_2<ext>`, ... (ordenados pela data de modificação).

    Args:
        pasta: pasta de download.
        novo_nome_base: novo nome, SEM extensão (ex.: "VELOE").
        arquivos_antes: foto da pasta tirada antes do download.
        quantidade_esperada: mínimo de arquivos novos esperados.
        timeout: tempo máximo de espera, em segundos.

    Returns:
        Lista com os novos caminhos.

    Raises:
        TimeoutError: se o download não finalizar.
        FileExistsError: se algum nome de destino já existir (nada é
            renomeado nem sobrescrito nesse caso).
    """
    novos = aguardar_novos_arquivos(
        pasta, arquivos_antes, quantidade_esperada, timeout
    )
    novos.sort(key=lambda arq: (arq.stat().st_mtime_ns, arq.name))

    destinos: list[Path] = []
    for indice, origem in enumerate(novos, start=1):
        sufixo_indice = '' if len(novos) == 1 else f'_{indice}'
        destinos.append(
            origem.with_name(
                f'{novo_nome_base}{sufixo_indice}{origem.suffix}'
            )
        )

    existentes = [destino for destino in destinos if destino.exists()]
    if existentes:
        logger.error('Destino(s) já existem: %s', existentes)
        raise FileExistsError(f'Destino(s) já existem: {existentes}')

    for origem, destino in zip(novos, destinos):
        origem.rename(destino)
        logger.info('Arquivo renomeado: %s -> %s', origem.name, destino.name)

    return destinos