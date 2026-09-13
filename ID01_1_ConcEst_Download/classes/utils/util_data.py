from datetime import datetime, timedelta

def obter_intervalo_ontem():
    """Gera o intervalo de datas baseado em D-1 no formato 'DD/MM/AAAA - DD/MM/AAAA'"""
    # Obtém a data de hoje e subtrai 1 dia
    ontem = datetime.now() - timedelta(days=1)
    
    # Formata no padrão brasileiro
    ontem_formatado = ontem.strftime('%d/%m/%Y')
    
    # Retorna o intervalo repetido
    return f"{ontem_formatado} - {ontem_formatado}"
