"""Utilitários para acesso ao Gerenciador de Credenciais do Windows.

Requer a biblioteca ``pywin32`` (``pip install pywin32``).

A credencial deve estar cadastrada no Windows como uma credencial genérica
(Painel de Controle > Contas de Usuário > Gerenciador de Credenciais >
Credenciais do Windows > Adicionar uma credencial genérica), onde:

- "Endereço de rede ou Internet" (TargetName) = nome_credencial (ex.: "site_Veloe")
- "Nome de usuário" = e-mail/usuário de login do site
- "Senha" = senha de login do site
"""

import logging

import win32cred

logger = logging.getLogger(__name__)


def obter_credencial_windows(nome_credencial: str) -> tuple[str, str]:
    """Recupera usuário e senha de uma credencial genérica do Windows.

    Args:
        nome_credencial: Nome (TargetName) da credencial cadastrada no
            Gerenciador de Credenciais do Windows (ex.: "site_Veloe").

    Returns:
        Tupla (usuario, senha) recuperada da credencial.

    Raises:
        ValueError: Se a credencial não for encontrada ou estiver incompleta.
        RuntimeError: Se ocorrer falha inesperada ao ler a credencial.
    """
    try:
        credencial = win32cred.CredRead(
            TargetName=nome_credencial,
            Type=win32cred.CRED_TYPE_GENERIC,
        )
    except win32cred.error as exc:
        logger.error("Falha ao ler credencial '%s': %s", nome_credencial, exc)
        raise ValueError(
            f"Credencial '{nome_credencial}' não encontrada no Gerenciador "
            "de Credenciais do Windows. Verifique se ela foi cadastrada "
            "como credencial genérica."
        ) from exc
    except Exception as exc:  # falha inesperada de baixo nível (win32 API)
        logger.error(
            "Falha inesperada ao acessar credencial '%s': %s",
            nome_credencial,
            exc,
        )
        raise RuntimeError(
            f"Falha inesperada ao acessar credencial '{nome_credencial}'."
        ) from exc

    usuario = credencial.get("UserName", "") or ""
    senha_bytes = credencial.get("CredentialBlob", b"") or b""
    senha = senha_bytes.decode("utf-16-le") if senha_bytes else ""

    if not usuario or not senha:
        raise ValueError(
            f"Credencial '{nome_credencial}' encontrada, mas usuário e/ou "
            "senha estão vazios."
        )

    logger.info("Credencial '%s' recuperada com sucesso.", nome_credencial)
    return usuario, senha


def obter_senha_windows(nome_credencial: str) -> str:
    """Recupera apenas a senha de uma credencial genérica do Windows.

    Args:
        nome_credencial: Nome (TargetName) da credencial cadastrada no
            Gerenciador de Credenciais do Windows (ex.: "site_Veloe").

    Returns:
        A senha armazenada na credencial.
    """
    _, senha = obter_credencial_windows(nome_credencial)
    return senha