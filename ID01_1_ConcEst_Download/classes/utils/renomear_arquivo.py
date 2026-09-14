import logging
from pathlib import Path
from time import sleep

logger = logging.getLogger(__name__)


def renomear_arquivo_mais_recente(
    pasta: str | Path,
    novo_nome_base: str,
) -> Path:
    """Renomeia o arquivo mais recente de uma pasta, mantendo a
    extensão original do arquivo (independente de qual for).

    Args:
        pasta: pasta onde procurar o arquivo mais recente.
        novo_nome_base: novo nome do arquivo, SEM extensão
            (ex.: "transacoes_estacionamento"). A extensão original
            do arquivo encontrado é preservada automaticamente.

    Returns:
        Path do arquivo já renomeado (novo caminho).

    Raises:
        NotADirectoryError: se pasta não for uma pasta.
        FileNotFoundError: se nenhum arquivo for encontrado.
    """
    sleep(3)
    pasta = Path(pasta)

    if not pasta.is_dir():
        logger.error("Caminho informado não é uma pasta: %s", pasta)
        raise NotADirectoryError(
            f"Caminho informado não é uma pasta: {pasta}"
        )

    arquivos = [item for item in pasta.iterdir() if item.is_file()]

    if not arquivos:
        logger.error("Nenhum arquivo encontrado em: %s", pasta)
        raise FileNotFoundError(f"Nenhum arquivo encontrado em: {pasta}")

    arquivo_mais_recente = max(
        arquivos, key=lambda arquivo: arquivo.stat().st_mtime
    )

    caminho_novo = pasta / f"{novo_nome_base}{arquivo_mais_recente.suffix}"
    arquivo_mais_recente.rename(caminho_novo)
    logger.info(
        "Arquivo renomeado: %s -> %s",
        arquivo_mais_recente.name,
        caminho_novo.name,
    )

    return caminho_novo