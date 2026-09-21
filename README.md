## Monitoramento Firebase (código-fonte)

O Android com pareamento QR e temas está em `android/`, adaptado ao Spark e sem notificações.
Veja [instalação, ativação do backend e testes](docs/android-monitor.md).

Configurações inclui monitoramento remoto opcional, com os mesmos temas do Windows.
Consulte [configuração e contrato de leitura Android](docs/firebase-monitoring.md).
Os executáveis existentes precisam ser recompilados para incluir esta funcionalidade.

## Versão v1.0.5 — distribuição portátil

Use `dist/DriveFlow-v1.0.5-portatil.exe`: copie **somente esse arquivo** para outro computador Windows 10/11 de 64 bits. Python, Qt e as demais bibliotecas já estão incluídos; não é necessário instalar bibliotecas. A extração automática inicial pode levar alguns segundos. Cada computador precisa da sua própria autenticação Google e acesso aos arquivos locais. Dados e credenciais ficam em `%LOCALAPPDATA%/DriveFlow`, separados do executável. Mantenha o executável em um local definitivo para abrir com o Windows.

Esta versão recupera falhas temporárias na renovação da autenticação antes e durante o upload. Uploads e consultas de pastas compartilham uma renovação sincronizada. Após a recuperação, o aplicativo consulta o progresso confirmado no Google antes de continuar. Uma recusa definitiva da autorização exige desconectar e conectar novamente, sem apagar a fila; os próximos itens não iniciam enquanto a autorização estiver recusada. O limite configurado de tentativas continua valendo: ao esgotá-lo, o item fica interrompido para retomada manual.

Os eventos de recuperação registram etapa, motivo seguro e offset. Falhas inesperadas registram o tipo de exceção sem a mensagem bruta, que poderia conter credenciais. O horário UTC do último bloco confirmado é persistido no banco e incluído nos diagnósticos; uploads antigos sem esse registro aparecem como `unknown` até confirmar outro bloco.

Ao pausar um upload, os itens aguardando também ficam pausados: nenhum próximo arquivo inicia até você clicar em play ou Continuar. Outros uploads já ativos continuam. A pasta definida em **Usar esta pasta** e seu caminho ficam verdes, mesmo ao selecionar outra pasta para navegação.

A conta salva é restaurada localmente, inclusive sem internet. Credenciais antigas são atualizadas após uma consulta bem-sucedida ao Google; se estiver offline, clique em Conectar conta para tentar novamente com a credencial existente. Não é necessário copiar o JSON OAuth a cada atualização. A pasta de dados e o usuário do Windows devem ser mantidos. A autorização ainda pode ser revogada pelo Google: projetos OAuth externos em modo **Teste** têm refresh tokens que expiram em 7 dias para os escopos do Drive. Consulte o [prazo de autorização do Google](https://developers.google.com/identity/protocols/oauth2#expiration) e configure o projeto para produção quando aplicável. Salvar o token em outra pasta não evita essa expiração.

A alternativa `dist/DriveFlow/DriveFlow.exe` continua disponível e exige sua pasta inteira. Feche a versão anterior antes de abrir a nova: ambas compartilham a mesma fila local e preservam suas configurações.

Na fila, **Continuar** adiciona os arquivos locais marcados e inicia os itens marcados. Cada item possui **play, pause, stop e remover**. Stop interrompe o agendamento/envio e mantém o registro e o progresso confirmado; play pode retomá-lo. Remover pede confirmação, solicita pausa e aguarda o bloco atual terminar antes de apagar o registro local. Não apaga arquivos locais ou remotos. Renomear e reiniciar sessões expiradas ficam no menu do botão direito.

O destino mostra a hierarquia de pastas e arquivos acessíveis ao aplicativo. Expanda as setas, selecione uma pasta e clique em **Usar esta pasta**. O conteúdo é atualizado após a conclusão do upload; **Atualizar** também consulta alterações externas. A permissão `drive.file` continua restringindo o conteúdo visível conforme a autorização Google existente.

**Gráficos** mostra cada upload ativo, com histórico dos últimos 2 minutos, eixo de velocidade em MiB/s e tempo relativo. As amostras representam a velocidade do último bloco confirmado, não a velocidade instantânea da placa de rede. O tempo decorrido soma o tempo ativo, incluindo tentativas de reconexão; pausas e tempo com o programa fechado são excluídos. Uploads anteriores a esta versão começam com tempo decorrido zero. A estimativa restante aparece quando existe velocidade mensurada. O ponto verde indica conta autenticada, não monitora continuamente a disponibilidade da internet.

Veja `CHANGELOG.md` para o histórico e a política de versionamento. `Compilar.bat` gera as duas distribuições.

# DriveFlow

Aplicativo desktop Windows para envio explícito de arquivos ao Google Drive, com fila SQLite, upload em blocos e retomada persistente. Criado a partir do [briefing compartilhado](https://chatgpt.com/share/6aaefe8d-8c44-83e9-89ae-8bda5ba04bb8).

## Abrir

- Versão compilada: `dist/DriveFlow/DriveFlow.exe`. Mantenha a pasta `_internal` junto ao executável.
- Código-fonte: execute `Instalar.bat` uma vez e depois `Iniciar.bat`.
- Terminal: `.venv\Scripts\python.exe -m driveflow`.

Requer Windows 10/11 x64. Para executar pelo código, Python 3.11 ou superior. Ambiente validado: Python 3.14, PySide6 6.11.2.

## Conectar o Google Drive

1. No [Google Cloud Console](https://console.cloud.google.com/), crie ou selecione um projeto.
2. Habilite a **Google Drive API** em APIs e serviços.
3. Configure o Google Auth Platform / tela de consentimento. Para uso pessoal em teste, adicione o e-mail que usará o aplicativo como usuário de teste. Em uma organização Workspace, use o tipo interno se disponível.
4. Crie um cliente OAuth do tipo **Aplicativo para computador / Desktop app** e baixe o JSON.
5. No DriveFlow, clique em **Conectar conta**, selecione o JSON e conclua a autorização no navegador.

O programa não solicita sua senha Google. O JSON não é incluído na distribuição. Tokens são protegidos com **Windows DPAPI**, vinculados ao usuário e à máquina. Não envie seu arquivo de credenciais em chats ou repositórios.

### O navegador recebeu a autorização, mas o aplicativo deu erro

A página de retorno no navegador apenas confirma que a resposta chegou. A conexão só está concluída quando seu e-mail aparece no DriveFlow. O aplicativo ainda precisa obter o token, consultar a Google Drive API e salvar a credencial.

- `AUTH_DRIVE_API_DISABLED`: ative **Google Drive API** em **APIs e serviços → Biblioteca**, no mesmo projeto do JSON. Depois tente conectar novamente com o mesmo JSON.
- `AUTH_DRIVE_HTTP_403`: o Google recusou o acesso ao Drive. Confira as permissões concedidas e eventuais restrições da conta Workspace.
- `AUTH_SCOPE_MISSING`: refaça a conexão e autorize as permissões solicitadas.
- Outros códigos `AUTH_…` identificam a etapa e o tipo de falha, sem incluir tokens ou códigos de autorização. Você pode copiar a mensagem para diagnóstico; ela também fica na aba Atividade.

Permissões adicionais que o Google já havia concedido não interrompem o login, desde que todas as permissões solicitadas estejam presentes.

### Pastas existentes e permissões

O padrão é `drive.file`: arquivos e pastas criados ou autorizados para o aplicativo. Você pode criar sua pasta de uploads pelo próprio programa. Pastas antigas podem não aparecer nesse modo.

Para navegar pelo Drive existente, ative **Configurações → Acessar pastas existentes de todo o Drive**, salve e reconecte. Esse modo solicita o escopo amplo `drive`, pois um navegador nativo de pastas arbitrárias não recebe acesso a elas somente com `drive.file`. A tela do Google mostra essa permissão; a escolha é explícita. O programa não implementa exclusão nem compartilhamento público de arquivos.

Projetos externos em modo de teste podem ter autorização com duração limitada; se a renovação falhar, reconecte a conta. A fila permanece salva. Distribuição externa pode exigir verificação do aplicativo pelo Google. Desconectar remove a credencial local; para revogar a concessão também no Google, use a página de conexões da sua Conta Google.

## Fluxo diário

1. Marque arquivos no explorador ou use **Selecionar arquivos**. A seleção é mantida ao navegar por unidades diferentes.
2. Navegue por duplo clique nas pastas do Drive e clique em **Usar esta pasta**. A raiz também pode ser selecionada explicitamente.
3. Clique em **Continuar**, no topo da fila. Esse único botão adiciona os arquivos locais selecionados ao destino e inicia os uploads marcados.
4. Os itens da fila vêm marcados por padrão. Desmarque os que não devem ser enviados; desmarcar um item aguardando ou ativo solicita sua pausa. Marcar novamente não inicia sozinho: clique em **Continuar**. Por padrão, só um arquivo é enviado de cada vez.
5. Consulte o **Histórico** para copiar o link ou abrir o arquivo no Drive. Compartilhe com o cliente pelas permissões do próprio Drive: copiar um link não torna o arquivo público.

Qualquer tipo de arquivo é aceito. O aplicativo não abre arquivos compactados e não conhece suas senhas.

## Recuperação e controles

- A sessão é salva antes de enviar o primeiro bloco. Cada atualização de progresso confirmada é gravada em SQLite com WAL e `synchronous=FULL`.
- Ao continuar, o programa consulta o servidor e usa o offset real recebido, inclusive se ele for diferente do checkpoint local.
- A criação usa um ID pré-alocado do Drive. Se a resposta final for perdida, o programa consulta esse ID antes de considerar novo envio. Isso evita uma cópia adicional por perda da confirmação.
- Falhas de rede, HTTP 429, 5xx e limites temporários causam novas tentativas com espera exponencial e jitter. Depois do limite, o item fica interrompido e pode ser continuado manualmente.
- Pausar/cancelar aguarda a requisição do bloco atual terminar ou atingir o timeout; não é instantâneo. O fechamento normal espera essa gravação. Uma queda abrupta é reconciliada com o servidor na próxima retomada.
- Ao reabrir, uploads pendentes ficam interrompidos, sem envio automático. As caixas de seleção são preservadas. Clique em **Continuar** para retomar apenas os itens marcados da conta conectada.
- Disco removido ou arquivo inacessível preserva a sessão. Reconecte o disco e clique em Continuar.
- Alteração no tamanho ou na data de modificação bloqueia a retomada. É preciso remover o item e adicioná-lo novamente. Não há hash completo: preserve os arquivos originais durante todo o envio.
- Sessões expiradas mantêm o progresso anterior como evidência. **Reiniciar sessão** pede confirmação e inicia o reenvio daquele item, se o Google já não tiver concluído o arquivo. Não há reinício silencioso.
- Um arquivo só é considerado concluído após consultar os metadados e verificar o tamanho no Drive.
- Nomes já existentes no destino são bloqueados antes de iniciar: use **Renomear** para escolher outro nome ou cancele. Esta versão não substitui arquivos existentes. A detecção abrange os arquivos visíveis no escopo OAuth concedido e não constitui um bloqueio contra criações simultâneas por outros programas.
- Cancelar e remover são ações locais. Não apagam conteúdo no Drive. Um bloco final que já tenha sido aceito pode resultar em arquivo concluído mesmo se você pedir cancelamento durante a requisição.
- Filas ficam vinculadas à conta que as criou. Outra conta não pode continuar esses envios.

O Google pode expirar sessões de upload; portanto a retomada depende de uma sessão ainda válida. Consulte a [documentação oficial de upload retomável](https://developers.google.com/workspace/drive/api/guides/manage-uploads).

## Interface e configurações

- Temas: azul profundo, cinza grafite, verde escuro e Spotify (preto/cinza com verde `#1DB954`); bordas com raio de 4–5 px.
- Indicadores agrupados em uma faixa compacta no topo; caixas de seleção persistentes na fila e uma única ação Continuar para envio.
- Ícone `upload.png` na marca lateral e na janela; ícone de disco do Windows no botão Unidades.
- Ícone próprio na barra de tarefas e no executável, usando `upload.ico` com tamanhos de 16 a 256 px e identificação do aplicativo no Windows. `tools/make_icon.py` gera o ICO a partir de `upload.png` durante a compilação.
- Menu lateral com os PNGs de 24 px fornecidos, em espaços iguais e sem deslocamento ao selecionar. A cor é aplicada na interface, preservando os arquivos originais: azul profundo `#66D7B0`, cinza grafite `#98BAFF`, verde escuro `#84D6AA`, Spotify `#1DB954`.
- Status compacto Conectado/Desconectado; a conta conectada aparece ao passar o mouse sobre o status.
- Abertura automática ao entrar no Windows, para o usuário atual. Pode ser desligada em **Configurações → Inicialização**. A inicialização não retoma uploads interrompidos automaticamente.
- Explorador local com caixas de seleção e tamanho; navegador do Meu Drive com paginação e criação de pastas.
- Progresso, bytes confirmados, velocidade média do último bloco, estimativa de tempo, estados e mensagens por arquivo.
- Barra com animação suave de 450 ms entre os valores confirmados, sem estimar bytes ainda não aceitos pelo Google. O percentual numérico continua mostrando o checkpoint confirmado.
- Até 3 uploads simultâneos; padrão de 1.
- Blocos configuráveis de 1 a 64 MiB; padrão de 8 MiB. O uso de memória é limitado aos blocos, não ao tamanho total do arquivo.
- Histórico, copiar link/ID e abertura do Drive.
- Atividade com exportação de eventos para um local escolhido. Os eventos são armazenados no banco local, sem tokens ou URLs de sessão.

### Velocidade

O software não aplica um teto fixo de velocidade de upload nem faz pausas deliberadas entre blocos bem-sucedidos. O padrão é um upload por vez, em blocos de 8 MiB. Cada bloco precisa ser confirmado pelo servidor antes do próximo; a leitura do disco, a latência, a conexão e o tempo de confirmação influenciam o desempenho. Os checkpoints também são gravados no SQLite. Blocos e simultaneidade são ajustáveis em Configurações. As esperas exponenciais ocorrem somente em falhas temporárias.

A interface mostra **MiB/s** (mebibytes por segundo), enquanto planos de internet normalmente usam **Mbps** (megabits por segundo). Por exemplo, 100 Mbps correspondem a aproximadamente 11,9 MiB/s antes das perdas de protocolo. O indicador é a média do último bloco confirmado, não uma medição instantânea da placa de rede.

## Dados locais

Pasta padrão: `%LOCALAPPDATA%\DriveFlow`.

- `queue.sqlite3` e arquivos WAL/SHM: fila, configurações, contas e eventos.
- `account.bin`: credencial cifrada por DPAPI.
- `application.lock`: trava de instância única, para não processar a mesma fila em dois programas.

As URLs de sessão também são cifradas. Nomes e caminhos dos arquivos no banco são metadados locais, não cifrados. Nenhum dado é enviado a intermediários ou serviços de telemetria. A comunicação externa do produto é direta com o Google.

A inicialização automática usa apenas o valor `DriveFlow` em `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`. Mantenha o executável na pasta atual; ao abrir o programa por um novo caminho, ele atualiza esse registro. Para remover a inicialização, desmarque a opção no aplicativo e salve antes de excluir a pasta do programa.

Não mova o banco para outro usuário/máquina esperando retomar sessões cifradas. Para backup consistente do banco, feche o aplicativo antes de copiar a pasta. O diretório pode ser substituído pela variável `DRIVEFLOW_DATA_DIR`, usada nos testes.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest pyinstaller
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m driveflow
```

`requirements-lock.txt` registra as versões exatas do ambiente de desenvolvimento. Execute `Compilar.bat` para gerar as distribuições em pasta e portátil usando PyInstaller. Use o arquivo `DriveFlow.spec` fornecido: ele evita que uma biblioteca ICU de outro programa no PATH seja incluída no lugar da biblioteca nativa do Windows exigida pelo Qt.

### Organização

- `storage.py`: banco e proteção DPAPI.
- `auth.py`: OAuth Desktop com PKCE, callback loopback e renovação de credenciais.
- `drive.py`: API e protocolo HTTP de sessões retomáveis.
- `upload.py`: validação, estados, retries, workers e agendamento.
- `widgets.py`, `ui.py`, `theme.py`: interface PySide6 e temas.
- `tests/`: recuperação, protocolo, segurança da sessão e teste de interface.

### Validação e limites da versão

Os testes locais usam um servidor simulado e arquivos temporários. Cobrem perdas de resposta, offset remoto divergente, reinicialização da fila, arquivo alterado, disco indisponível, expiração, erro de tamanho, duplicidade, limite de tentativas, conta incorreta e criptografia DPAPI. Um arquivo esparso de 100 GiB testa offset de 64 bits e leitura limitada do trecho final; **não representa um envio real de 100 GiB ao Google**.

Antes de usar com dados de clientes, valide com sua conta e arquivos descartáveis:

- Enviar um arquivo, interromper a rede e reconectar.
- Pausar, fechar, reabrir e continuar.
- Interromper o processo/reiniciar o Windows durante envio e retomar.
- Desconectar/reconectar um HD externo e retomar.
- Alterar um arquivo pausado e conferir o bloqueio.
- Enviar um arquivo grande real e conferir tamanho, conteúdo e permissões no Drive.

Esses testes reais dependem da credencial e autorização Google do usuário e não foram executados automaticamente. O navegador inicial abrange Meu Drive; não há seletor dedicado de Shared Drives, limite de banda, atualização automática ou substituição de arquivos remotos nesta versão.

Referências: [OAuth para aplicativos desktop](https://developers.google.com/identity/protocols/oauth2/native-app), [escopos do Google Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
