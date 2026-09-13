"""Utilitário simples para limpar arquivos de um diretório."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def limpar_diretorio(diretorio: Path) -> None:
    """Apaga todos os arquivos dentro de um diretório (recursivamente),
    preservando a estrutura de subpastas.

    Args:
        diretorio: Caminho do diretório a ser limpo.
    """
    for arquivo in Path(diretorio).rglob("*"):
        if arquivo.is_file():
            try:
                arquivo.unlink()
                logger.info("Apagado: %s", arquivo)
            except OSError as exc:
                logger.error("Falha ao apagar '%s': %s", arquivo, exc)