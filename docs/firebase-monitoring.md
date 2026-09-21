# Monitoramento remoto

O módulo `driveflow/firebase_monitor.py` observa a fila SQLite através de um callback
protegido. O motor de uploads e o OAuth do Drive não foram alterados. A tela
Configurações usa os temas existentes e salva `remote_monitoring` no banco local.
O JSON em `config/remote-monitoring.example.json` documenta o formato; não é
carregado automaticamente. Alterações na tela passam a valer ao reabrir o programa.

## Ativar

1. No ambiente Python, execute `.venv\Scripts\python.exe -m pip install -r requirements-monitoring.txt`.
2. Crie um banco Cloud Firestore no projeto Firebase e uma conta de serviço exclusiva
   para publicação, com permissão IAM para gravação no Firestore (por exemplo,
   `roles/datastore.user`). Essa função permite mais operações do que este módulo
   usa; limite o acesso à conta de serviço e ao projeto.
3. Guarde o JSON de serviço fora do repositório e da distribuição, acessível somente
   ao usuário Windows. Nunca use o JSON OAuth do Drive nesse campo.
4. Em Configurações, informe nome, ID exclusivo e caminho da credencial, marque
   monitoramento, salve e reabra. Caminhos relativos são resolvidos na pasta de dados
   `%LOCALAPPDATA%/DriveFlow` (ou `DRIVEFLOW_DATA_DIR`). O ID inicial é um UUID
   persistido; ao copiar configurações para outro PC, atribua outro ID.

Sem ativação não existe conexão nem importação do SDK. Sem SDK, arquivo ou permissão,
o aplicativo continua e registra `FIREBASE_MONITOR_ERROR` em Atividade. Instale as
dependências de monitoramento antes de compilar para incluí-las no executável.
Os executáveis já existentes em `dist` não contêm esta implementação.

## Contrato para o Android futuro

Cada publicação substitui `computers/{computer_id}`, com timestamp do servidor.
Todos os campos solicitados são enviados; tamanho e velocidade estão em bytes e
bytes/s, e estimativa em segundos (`null` quando não há velocidade conhecida).
Não são enviados caminhos locais, conta Google, IDs/sessões do Drive, mensagens de
erro, tokens ou credenciais. Nome de arquivo e destino são visíveis aos leitores.

Durante preparação/upload há publicação aproximadamente a cada 5 segundos,
mesmo durante um bloco longo. Alterações de estado da fila acordam o publicador
imediatamente, sem esperar o intervalo; a requisição acontece na thread de
monitoramento. Em falhas, há nova tentativa após o intervalo. Existe somente um
snapshot pendente: estados intermediários podem ser substituídos enquanto a rede
estiver ocupada. Estados estáveis inativos não geram gravações periódicas.

Com uploads simultâneos, os campos `current_*`, progresso, velocidade e estimativa
representam o primeiro arquivo em envio na ordem da fila, ou o primeiro ativo em
preparação. A conclusão/pausa de outro arquivo dispara uma atualização, mas o
computador continua `uploading` enquanto existir arquivo enviando. `queue_total`
conta todos os registros locais; `queue_remaining` conta habilitados não concluídos
nem cancelados. Cancelamento é mapeado para `idle` quando não há trabalho pendente;
pausa e cancelamento refletem a confirmação do bloco atual, como no app Windows.
Erros locais são mapeados para `error`; estados de retomada para `preparing`.

No fechamento há tentativa de publicar `offline` sem bloquear o encerramento.
Queda de energia, encerramento abrupto ou rede indisponível podem impedir essa
gravação. O Android deve mostrar estado desatualizado para uploads/preparações com
`last_update` antigo (por exemplo, mais de 30 segundos). Um estado `idle` antigo
não prova que o PC está offline, pois não há heartbeat ocioso.

## Acesso somente de leitura (pareamento QR)

As regras em `config/firestore.rules` e `firebase/firestore.rules` exigem Firebase
Authentication e um vínculo individual em `readers/{uid}/computers/{computerId}`.
O Android cria o vínculo por transação validada pelas regras, ao consumir o QR code do Windows. Login anônimo sozinho
não dá acesso a nenhuma máquina. Os clientes não podem escrever telemetria nem
criar vínculos sem um código válido. Consulte [o guia Android](android-monitor.md) para ativar no Spark.
Nunca distribua a conta de serviço no Android.

Bibliotecas de servidor ignoram Security Rules e usam IAM: as regras de leitura
não restringem a conta de serviço do Windows. Referências oficiais:
[regras e autenticação](https://firebase.google.com/docs/firestore/security/overview),
[claims e bibliotecas de servidor](https://firebase.google.com/docs/firestore/security/rules-fields),
[gravação com timeout](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.document.DocumentReference).

O aplicativo Android agora está em `android/`; a publicação das regras
continua sendo uma etapa de ativação. Cloud Functions não são usadas nesta versão. Os testes automatizados usam publicador simulado
e emulador; a validação ponta a ponta exige regras publicadas, login anônimo habilitado e celular conectado.
