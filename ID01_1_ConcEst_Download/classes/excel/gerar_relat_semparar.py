import logging
import sqlite3
from pathlib import Path

from openpyxl import Workbook

logger = logging.getLogger(__name__)

NOME_TABELA_SEMPARAR = "tbl_cred_semparar"
NOME_ARQUIVO_EXCEL_SEMPARAR = "SEMPARAR.xlsx"


def exportar_tbl_cred_semparar_para_excel(
    caminho_banco: Path,
    diretorio_destino: Path,
    nome_arquivo: str = NOME_ARQUIVO_EXCEL_SEMPARAR,
) -> Path:
    """Exporta todos os registros e colunas da tabela tbl_cred_semparar
    para um arquivo Excel (.xlsx).

    Args:
        caminho_banco: caminho do banco de dados SQLite
            (ex.: banco_dados.db).
        diretorio_destino: pasta onde o arquivo .xlsx será salvo
            (ex.: InitAllSettings.config['arquivos_baixados']).
        nome_arquivo: nome do arquivo de saída. Padrão: SEMPARAR.xlsx.

    Returns:
        Path do arquivo .xlsx gerado.

    Raises:
        sqlite3.OperationalError: se a tabela não existir ou houver
            erro na consulta.
    """
    diretorio_destino = Path(diretorio_destino)
    diretorio_destino.mkdir(parents=True, exist_ok=True)
    caminho_arquivo_excel = diretorio_destino / nome_arquivo

    conexao = sqlite3.connect(caminho_banco)
    try:
        cursor = conexao.cursor()
        try:
            cursor.execute(f"SELECT * FROM {NOME_TABELA_SEMPARAR}")
        except sqlite3.OperationalError:
            logger.error(
                "Erro ao consultar a tabela '%s' em %s",
                NOME_TABELA_SEMPARAR,
                caminho_banco,
            )
            raise

        nomes_colunas = [descricao[0] for descricao in cursor.description]
        linhas = cursor.fetchall()
    finally:
        conexao.close()

    planilha = Workbook()
    aba = planilha.active
    aba.title = "SemParar"

    aba.append(nomes_colunas)
    for linha in linhas:
        aba.append(linha)

    planilha.save(caminho_arquivo_excel)
    logger.info(
        "Arquivo Excel gerado: %s (%s registros)",
        caminho_arquivo_excel,
        len(linhas),
    )

    return caminho_arquivo_excel