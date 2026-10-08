# ID01_1_ConcEst_Download — Documentação do Projeto

> Documentação gerada a partir da leitura do código-fonte, do `Config.xlsx`, dos scripts SQL, do histórico Git e do log de execução de 08/10/2026 contidos no arquivo `ID01_1_ConcEst_Download.zip`.
> Nenhum arquivo do projeto foi alterado. Segredos e credenciais **não** são reproduzidos aqui.

---

## 1. Visão geral

| Item | Valor |
|---|---|
| Nome do projeto | `ID01_1_ConcEst_Download` |
| Descrição | Baixa, a cada execução, os relatórios de transações de estacionamento (D-1) de cada adquirente, preparando os arquivos para a etapa seguinte de conciliação (`ID01_2_ConcEst_TratarDados`) |
| Cliente | Partage (`Details_Project.json`) |
| Ferramenta | Python RPA (framework próprio, sem orquestrador externo) |
| Automação web | Selenium 4.28.1 + `webdriver-manager` (Chrome) |
| Sistemas de interação | Excel, SQLite, sites das adquirentes, Microsoft Graph (e-mail) |
| Tipo de fila | SQLite (`tbl_Fila_Processamento`) |
| Versão | `1.0.0` (arquivo `VERSION`) |
| Python | 3.13 (bytecode `cpython-313` nos `__pycache__`) |
| Plataforma | Windows (usa `win32cred`, `tkinter`, caminhos `C:\...`, `chrome.exe`, `excel.exe`) |
| Repositório | GitHub (`origin/main`), 4 commits |
| Equipe (README) | GP / RO / DEV: Felipe Mello |

### O que o robô faz, em uma frase

Para cada uma das seis adquirentes — **Sem Parar, Veloe, Conectcar, GreenPass, Bradesco e Cielo** — o robô obtém o arquivo de movimentação do dia anterior (via portal web ou via e-mail), salva na pasta `arquivos_baixados` e o renomeia para `<ADQUIRENTE>.<extensão>`.

---

## 2. Arquitetura

O projeto segue um framework de RPA no estilo **REFramework** (Initialization → Loop de itens da fila → End Process), com a fila em SQLite.

```
__main__.py / bot.py
        │
        ▼
 Bot.action()
   ├── Initialization.execute()      ← prepara ambiente, fila e navegador
   ├── LoopStation.execute()         ← processa 1 item de fila por adquirente
   │       └── Process.execute()     ← login + navegação + download + renomear
   └── EndProcess.execute()          ← fecha apps, relatórios, e-mail final, status
```

### 2.1 Ponto de entrada

- `python -m ID01_1_ConcEst_Download` executa `__main__.py`, que chama `Bot.main()` (ou `Bot.action(None)` quando recebe `--execution` com 5+ argumentos).
- `Bot.action()` envolve Initialization + LoopStation em `try/except` (`TerminateException` e `Exception`) e **sempre** executa `EndProcess.execute()` em seguida.

### 2.2 Initialization (`classes/framework/Initialization.py`)

Sequência executada:

1. Registra no log informações do sistema, uso do computador e monitores.
2. Inicia o **Robot Stream** (se `IniciarRobotStream = SIM`).
3. Faz **backup do SQLite** (se `BackupSqlite = SIM`, atualizando a cada 3 dias).
4. Insere o registro da execução em `tbl_dados_execucao`.
5. Envia e-mail inicial (se `EmailInicial = SIM`).
6. Inicia a **gravação de tela** (se `GravarTela = SIM`).
7. Finaliza `excel.exe` e `winword.exe` (`KillAllProcesses`).
8. Chama `InitAllApplications.execute(first_run=True)`.
9. Atualiza a quantidade de itens a processar.

Em caso de erro, captura screenshot (se `CapturarScreenshot = SIM`), envia e-mail de erro (se `EmailErroInicializacao = SIM`), grava a exceção em `tbl_dados_execucao` e relança.

### 2.3 InitAllApplications (`classes/framework/InitAllApplications.py`)

Na **primeira execução** (`first_run=True`), `add_to_queue()`:

1. `QueueManager.abandon_queue()` — marca itens `NEW` remanescentes como `ABANDONED`.
2. `QueueManager.delete_tbl_cred_semparar()` — esvazia a tabela `tbl_cred_semparar`.
3. `limpar_diretorio(arquivos_baixados)` — **apaga todos os arquivos** da pasta de downloads (recursivo).
4. Cria um item de fila por adquirente, nesta ordem: `SEM PARAR`, `VELOE`, `CONECTCAR`, `GREENPASS`, `BRADESCO`, `CIELO`. Cada item tem `referencia = <adquirente>` e `info_adicionais = {"adquirente": "<adquirente>"}`.

Depois abre o **Chrome** (`headless=False`) com a pasta de download configurada, com até `MaxRetryNumber` tentativas.

> Existe uma linha comentada para testar uma única adquirente (`adquirente_lista = ['BRADESCO']`) e a constante `ADQUIRENTE_TESTE` em `Process.py` com a mesma finalidade.

### 2.4 LoopStation (`classes/framework/LoopStation.py`)

Para cada item obtido em `GetTransaction`:

- Até `MaxRetryNumber` (3) tentativas por item.
- **Sucesso** → `QueueManager.update_status_item()` e `DadosExecucao.update_tabela_dados_itens('SUCESSO')`.
- **`BusinessRuleException`** → não repete; captura screenshot, mata `chrome.exe`, marca o item com erro de negócio e segue (`break`).
- **`TerminateException`** → considera o item como sucesso (parada antecipada intencional).
- **`Exception` (sistema)** → registra log/screenshot, mata `chrome.exe`, reinicia o navegador via `InitAllApplications.execute(first_run=False)` e tenta de novo; na última tentativa marca o item com erro.
- Se `MaxConsecutiveSystemExceptions` (3) itens consecutivos falharem por erro de sistema, o loop é interrompido.

### 2.5 Process (`classes/framework/Process.py`)

Contém o mapa `ADQUIRENTES` (dataclass `Adquirente` com `nome_log`, `login`, `navegar`):

| Adquirente (chave) | Login | Navegação / download |
|---|---|---|
| `VELOE` | `fazer_login_veloe` | `navegar_aba_repasse_lanc` |
| `GREENPASS` | `fazer_login_greenpass` | `navegar_aba_estadia_taggy` |
| `SEM PARAR` | `fazer_login_semparar` | `navegar_aba_transacoes_semparar` |
| `CONECTCAR` | `fazer_login_conectcar` | `navegar_aba_transacoes` |
| `CIELO` | — | `cielo_email.buscar_arquivos_email()` |
| `BRADESCO` | — | `bradesco_email.buscar_email_bradesco()` |

Fluxo de `Process.execute()`:

1. Lê a adquirente do item da fila (`info_adicionais['adquirente']`, em maiúsculas); se não existir no mapa → `BusinessRuleException('Adquirente inválida: ...')`.
2. Executa `login(driver)` e `navegar(driver)`, quando definidos.
3. Chama `renomear_arquivo_mais_recente(pasta=arquivos_baixados, novo_nome_base=<adquirente>)`.

### 2.6 EndProcess (`classes/framework/EndProcess.py`)

1. Fecha aplicações e mata `chromedriver.exe`.
2. Finaliza a gravação de tela (se ativa).
3. Atualiza `tbl_dados_execucao` com fim, contadores e tempo.
4. Gera os relatórios **analítico** e **sintético** (`Relatorios`).
5. Envia e-mail final com os relatórios anexos (se `EmailFinal = SIM`) e remove os arquivos gerados.
6. Se `RelatorioRAAS = SIM` e não for execução de teste, gera CSVs e envia por SMTP para cobrança RAAS.
7. Registra o resultado final em `ExecutionControl.finish_task` (sucesso / falha na inicialização / falha no processamento).

---

## 3. Módulos por adquirente (`classes/sites/`)

Todos os módulos de portal web reutilizam o `InitAllSettings.web_driver` já aberto e fazem login com **até 3 tentativas** (espera de 3 s entre elas, timeout de 20 s).

### 3.1 Sem Parar — `semparar.py`

- **Portal:** `credenciados.semparar.com.br` (login → `/transactions`).
- **Captcha:** exibe a janela `aguardar_resolucao_captcha()` e pausa até o operador resolver manualmente.
- **Período:** D-1 (`obter_data_ontem`), escolhido no calendário Angular Material.
- **Particularidade:** não baixa arquivo do portal. Para **cada credenciado** listado no dropdown, o robô filtra, aguarda o "valor total" estabilizar (3 leituras iguais, 3 s entre leituras) e grava em `tbl_cred_semparar` (`credenciado`, `valor_total`, `data_periodo`, `ultima_atualizacao`).
- **Saída:** `exportar_tbl_cred_semparar_para_excel` gera `SEMPARAR.xlsx` (aba `SemParar`) na pasta `arquivos_baixados`.

### 3.2 Veloe — `veloe.py`

- **Portal:** `beta-portal-ec.veloe.com.br` (Portal Estabelecimentos Comerciais).
- **Fluxo:** abre *Repasses → Lançamentos* → **Buscar** → botão de download → vai para **Arquivos** → aguarda a primeira linha ficar com status `Sucesso` (recarrega a página a cada 5 s, timeout de 300 s) → clica no ícone de download.
- Usa busca em *shadow DOM* para componentes `vlv-*`.

### 3.3 Conectcar — `conectcar.py`

- **Portal:** `conveniado.conectcar.com`.
- **Captcha:** aguarda resolução manual (`aguardar_resolucao_captcha`).
- **Fluxo:** *Consultar Transação Estacionamento* → fecha pop-up → seleciona **todos** os conveniados → período D-1 → Pesquisar → fecha modal "relatório solicitado" → **Central de Arquivos** → aguarda a primeira linha sair de "Processando" para "Download" (polling de 5 s, timeout de 420 s) → baixa.
- **Pós-processamento:** localiza o `.zip` mais recente, descompacta, move os arquivos extraídos para a raiz da pasta de downloads (pasta extraída com prefixo `Transacoes_`).

### 3.4 GreenPass — `greenpass.py`

- **Portal:** `conveniado.greenpass.com.br` (`/TaggyStayHistory`).
- **Fluxo:** preenche o período D-1 (`DD/MM/AAAA - DD/MM/AAAA`), filtra e baixa em formato **.xlsx** pelo menu de download.
- Arquivo gerado pelo portal no padrão `EstadiaTaggy_<data> - <data>.xlsx`.

### 3.5 Cielo (e-mail) — `cielo_email.py`

Sem navegador. Usa **Microsoft Graph API** (OAuth2 client credentials).

1. Lê credenciais do Windows Credential Manager.
2. Obtém token e lista **mensagens não lidas** do remetente `extrato@cielo.com.br`, cujo assunto começa com *"Cliente Cielo, confira seu relatório recorrente de vendas e recebíveis"* (comparação sem acento e sem diferenciar maiúsculas).
3. Para cada mensagem (da mais antiga para a mais nova): baixa o CSV do anexo, ou, se não houver, pelo link "CSV" no corpo do e-mail.
4. **Só marca como lida após o download com sucesso.** Em falha, a mensagem permanece não lida para a próxima execução.
5. Sessão HTTP com retry exponencial (5 tentativas; códigos 429/500/502/503/504).

Permissão necessária no Azure (Application): **`Mail.ReadWrite`**.

### 3.6 Bradesco (e-mail) — `bradesco_email.py`

Mesma estrutura do módulo Cielo, com estas diferenças:

- Remetente: `automacao@partage.com.br`; assunto começa com *"Arquivo Retorno Bradesco PIX"*.
- Baixa **todos os anexos de arquivo** (ignora imagens inline).
- Exemplo de arquivo observado no log: `consolidado_bradesco_<data>.csv`.

---

## 4. Configuração

### 4.1 `resources/config/Config.xlsx`

Carregado por `InitAllSettings.load_config()`. Abas: **Settings**, **Constants**, **Credentials**, **Assets** (colunas `Name | Value | Description`).

| Chave | Valor atual | Função |
|---|---|---|
| `NomeProcesso` | `ID01_1_ConcEst_Download` | Nome do processo |
| `FilaProcessamento` | *(vazio)* | Vazio → usa `tbl_Fila_Processamento` |
| `CaminhoBancoSqlite` | `C:\Armazenamento\ID01_1_ConcEst_Download\Banco Dados\banco_dados.db` | Banco SQLite em uso (fora do `resources`) |
| `arquivos_baixados` | `C:\Armazenamento\ID01_1_ConcEst_Download\Arquivos_Baixados` | Pasta de destino dos downloads |
| `CaminhoAnexo` | `...\Anexos` | Saída de anexos |
| `CaminhoExceptionScreenshots` | `...\Screenshots` | Screenshots de erro |
| `CaminhoPastaRelatorios` | `...\Relatorios` | Relatórios analítico/sintético |
| `CaminhoPastaLogs` | `...\Logs` | Pasta de logs configurada |
| `CaminhoSalvarVideo` | `...\Videos` | Gravação de tela |
| `usuarios` | e-mail da conta de automação | Usuário usado nos logins dos portais |
| `EmailCredenciais` | e-mail da conta de automação | Caixa de entrada lida via Graph |
| `EmailDestinatarios` | e-mail(s) | Destinatários dos avisos |
| `EmailInicial` / `EmailCadaErro` / `EmailErroInicializacao` / `EmailFinal` | `NÃO` | Controle de e-mails |
| `CapturarScreenshot` | `NÃO` | Screenshot em erro |
| `GravarTela` | `NÃO` | Gravação de tela |
| `IniciarRobotStream` | `NÃO` | Robot Stream |
| `BackupSqlite` | `NÃO` | Backup do SQLite |
| `RelatorioRAAS` | `NÃO` | Envio de dados RAAS (SMTP `smtp.office365.com:587`) |
| `AtivarLogs` | `NÃO` | Log de métodos e tempos |
| `NomeTabelaDadosExecucao` | `tbl_dados_execucao` | Tabela de execuções |
| `NomeTabelaDadosItens` | `tbl_dados_itens_fila` | Tabela de itens |
| `MaxRetryNumber` | `3` | Tentativas por item |
| `MaxConsecutiveSystemExceptions` | `3` | Limite de erros de sistema consecutivos (0 desativa) |
| `MaxTimeoutRequests` | `30` | Timeout de requests (s) |
| `NomeCliente` | `IAFastLab` | Nome do cliente nos relatórios |

> A aba **Credentials** está vazia: nenhuma senha fica no `Config.xlsx`.

### 4.2 Credenciais (Windows Credential Manager)

Todas as credenciais ficam no **Gerenciador de Credenciais do Windows**, como *credencial genérica* (Endereço de rede = nome abaixo; usuário e senha da conta).

| Uso | Nome da credencial (TargetName) |
|---|---|
| Veloe | `site_Veloe` |
| Sem Parar | `site_semparar` |
| Conectcar | `site_conectcar` |
| GreenPass | `site_greenpass` |
| Graph (Cielo/Bradesco) | `GRAPH_CLIENT_ID`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_BASE_URL` |

---

## 5. Banco de dados SQLite

Arquivo-modelo em `resources/sqlite/banco_dados.db` (o banco em produção é o apontado por `CaminhoBancoSqlite`).

| Tabela | Finalidade |
|---|---|
| `tbl_Fila_Processamento` | Fila: `id`, `referencia`, `datahora_criado`, `nome_maquina`, `info_adicionais` (JSON), `status`, `obs`, `ultima_atualizacao` |
| `tbl_dados_execucao` | Uma linha por execução: GUID, máquina, resolução, runner, início/fim, tempo, contadores (fila/sucesso/business/app), exceção de inicialização |
| `tbl_dados_itens_fila` | Uma linha por tentativa de item: início/fim, tempo, referência, detalhes, status, tipo e descrição da exceção, screenshot |
| `tbl_cred_semparar` | Valor total por credenciado do Sem Parar (`credenciado`, `valor_total`, `data_periodo`, `ultima_atualizacao`) |

**Ciclo de status dos itens da fila:** `NEW` → `ON QUEUE` (reservado para a máquina/GUID da execução) → `RUNNING` → resultado final. Itens `NEW` de execuções anteriores viram `ABANDONED` no início.

> O `banco_dados.db` do template contém `tbl_Fila_Processamento`, `tbl_dados_execucao` e `tbl_dados_itens_fila`, mas **não** contém `tbl_cred_semparar`. Ela precisa existir no banco apontado por `CaminhoBancoSqlite`.

Scripts SQL em `resources/scripts/analitico_sintetico/`:

| Script | Uso |
|---|---|
| `Script_Select_Analitico.sql` | Dados do relatório analítico (itens por execução) |
| `Script_Select_Sintetico.sql` | Dados do relatório sintético (resumo da execução) |
| `Script_Select_CapturaQtdItens.sql` | Contagem de sucesso / negócio / sistema (último status de cada item) |
| `Script_Update_DadosExecucao.sql` | Atualização do fechamento da execução |

---

## 6. Estrutura de pastas

```
ID01_1_ConcEst_Download/
├── ID01_1_ConcEst_Download/              ← pacote Python
│   ├── __main__.py                       ← entrada (python -m)
│   ├── bot.py                            ← classe Bot (orquestra init/loop/fim)
│   ├── classes/
│   │   ├── chrome/google/Homepage.py
│   │   ├── dados_execucao/DadosExecucao.py   ← tabelas de execução/itens
│   │   ├── databases_manager/            ← SQLite, SQL Server, MariaDB
│   │   ├── email/receive|send/           ← SMTP, Outlook COM, Outlook API
│   │   ├── excel/                        ← openpyxl, xlwings, gerar_relat_semparar
│   │   ├── framework/                    ← Initialization, LoopStation, Process, EndProcess, ...
│   │   ├── queue/                        ← QueueManager (+ Performer)
│   │   ├── relatorios/Relatorios.py      ← analítico / sintético / RAAS
│   │   ├── sites/                        ← veloe, semparar, conectcar, greenpass, cielo_email, bradesco_email
│   │   └── utils/                        ← Log, Exceptions, Credenciais, captcha, datas, backup, ...
│   └── resources/
│       ├── config/Config.xlsx
│       ├── logs/execucao_AAAAMMDD.log
│       ├── relatorios/                   ← saída de relatórios
│       ├── robot_stream/                 ← StreamRobotScreen.exe
│       ├── scripts/analitico_sintetico/  ← SQLs
│       ├── sqlite/banco_dados.db         ← banco-modelo
│       ├── templates/                    ← e-mails (.txt) e relatórios (.xlsx)
│       └── videos/
├── Details_Project.json                  ← metadados do projeto
├── README.md   VERSION   requirements.txt
├── setup.py    MANIFEST.in   build.bat   build.sh
└── .gitignore
```

---

## 7. Dependências

`requirements.txt`:

| Pacote | Versão |
|---|---|
| selenium | 4.28.1 |
| webdriver-manager | 4.0.2 |
| pandas | 2.3.1 |
| openpyxl | 3.1.5 |
| pyodbc | 5.2.0 |
| opencv-python | 4.12.0.88 |
| pyautogui | 0.9.54 |
| msal | 1.32.3 |
| beautifulsoup4 | 4.13.4 |
| screeninfo | 0.8.1 |
| xlwings | 0.33.15 |
| setuptools | 80.9.0 |
| mysql-connector-python | 9.3.0 |
| psutil | 6.1.1 |
| numpy | 2.2.1 |

Usados no código **mas ausentes** do `requirements.txt`: `requests` e `pywin32` (módulos `win32cred`) — ver seção 10.

Requisitos do ambiente: Windows, Google Chrome instalado, Excel/Word (o framework encerra `excel.exe`/`winword.exe`), acesso à internet e às URLs dos portais.

---

## 8. Instalação e execução

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Instalar o projeto e as dependências
pip install -e .
pip install requests pywin32        # ausentes do requirements.txt

# 3. Cadastrar as credenciais no Gerenciador de Credenciais do Windows
#    (site_Veloe, site_semparar, site_conectcar, site_greenpass, GRAPH_*)

# 4. Ajustar resources/config/Config.xlsx (caminhos, e-mails, flags SIM/NÃO)

# 5. Executar
python -m ID01_1_ConcEst_Download
```

Geração do pacote de distribuição: `build.bat` (Windows) ou `build.sh` → `python setup.py sdist`.

**Execução assistida:** nos portais Sem Parar e Conectcar o robô abre a janela *"Ação manual necessária"* e aguarda o operador resolver o captcha e clicar em **Continuar**. Fechar a janela pelo "X" gera `CaptchaNaoConfirmadoError`.

---

## 9. Logs, relatórios e saídas

- **Log:** `resources/logs/execucao_AAAAMMDD.log` (console + arquivo), formato `DD/MM/AAAA HH:MM:SS - NÍVEL - mensagem`.
- **Relatórios:** analítico e sintético a partir dos templates `Relatorio_Analitico.xlsx` / `Relatorio_Sintetico.xlsx`.
- **Arquivos de saída** (em `arquivos_baixados`), após a execução bem-sucedida, exemplo do log de 08/10/2026:

| Adquirente | Arquivo final |
|---|---|
| Sem Parar | `SEM PARAR.xlsx` / `SEMPARAR.xlsx` (gerado a partir do SQLite) |
| Veloe | `VELOE.<ext>` |
| Conectcar | `CONECTCAR.<ext>` |
| GreenPass | `GREENPASS.xlsx` |
| Bradesco | `BRADESCO.csv` |
| Cielo | `CIELO.csv` |

Execução registrada em 08/10/2026 (trecho final do log): 6 de 6 itens processados e task finalizada com sucesso.

---

## 10. Pontos de atenção observados na leitura

Estes itens são **observações** para avaliação; nada foi alterado no projeto.

1. **Retorno ignorado nas adquirentes por e-mail.** `buscar_arquivos_email()` e `buscar_email_bradesco()` retornam `1` quando há falha, mas o `Process` descarta esse retorno (`lambda driver: ...`). Uma falha parcial pode terminar como item `SUCESSO`.
2. **Renomeação pode pegar o arquivo errado.** `renomear_arquivo_mais_recente` renomeia o arquivo mais recente da pasta, que é compartilhada entre adquirentes. Se Cielo ou Bradesco não tiverem e-mail novo, o "mais recente" pode ser o arquivo da adquirente anterior, que seria renomeado indevidamente.
3. **`requirements.txt` incompleto.** Faltam `requests` e `pywin32`, usados pelos módulos de e-mail (Graph) e de credenciais.
4. **Banco-modelo sem `tbl_cred_semparar`.** O `resources/sqlite/banco_dados.db` não tem a tabela usada pelo Sem Parar.
5. **`Config.xlsx` e `banco_dados.db` versionados.** O `.gitignore` ignora `*.log`, mas não `Config.xlsx` nem `.db`; o `Config.xlsx` contém e-mails reais da conta de automação e dos destinatários. Vale avaliar a política do repositório.
6. **Seletores XPath absolutos.** Muitos seletores (`/html/body/div[...]`) dependem da estrutura exata das páginas e quebram com qualquer ajuste de layout dos portais.
7. **`time.sleep` fixos.** Há várias esperas fixas (GreenPass, Conectcar, Sem Parar) em vez de esperas por condição.
8. **Veloe em ambiente beta.** A URL usada é `beta-portal-ec.veloe.com.br`.
9. **Período fixo em D-1.** O intervalo de datas não é parametrizável; reprocessar outro dia exige alterar o código.
10. **Valor do Sem Parar gravado como texto.** `valor_total` é convertido para string com vírgula antes do `INSERT`.
11. **Limpeza destrutiva da pasta de downloads.** `limpar_diretorio` apaga todos os arquivos da pasta no início de cada execução (comportamento intencional, mas relevante para quem usa a pasta manualmente).
12. **Documentação de manutenção.** O `README.md` mantém os blocos de *Releases* como placeholders e o `MANIFEST.in` referencia `README.rst`, que não existe (o arquivo é `README.md`). Em `ExecutionControl`, `versao_runner` está como `X.X.X`.
13. **Código legado do template.** Permanecem classes do framework original não usadas neste fluxo (SQL Server, MariaDB, Outlook COM/API, `QueueManagerPerformer`, `Homepage`).

---

## 11. Histórico Git

| Ordem | Mensagem do commit |
|---|---|
| 1 | `first commit` |
| 2 | `adiciona processo semparar` |
| 3 | `adiciona script limpar tabela` |
| 4 | `adiciona tela aviso captcha` |

Branch principal: `main` (remoto `origin` no GitHub).
