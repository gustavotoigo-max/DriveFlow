# Histórico de versões

## Próxima versão (não publicada)

- Botão **Compactar** acima da fila: compacta uma pasta com o WinRAR instalado (RAR ou ZIP, método, dicionário 4096 KB, volumes de 20, 25, 30 GB ou personalizado, senha). Fica apagado quando o WinRAR não é encontrado.
- Cada volume entra na fila e começa a subir assim que o WinRAR passa para o próximo. A barra de compactação aparece acima da de upload.
- Botão **Iniciar** quando nada foi interrompido; **Continuar** só quando há envio pausado ou parado.
- Barras de progresso redesenhadas no padrão Nexotool, com o % no centro.
- Janelas internas (avisos, perguntas, Compactar, celular) sem a barra do Windows, no padrão da janela principal, com os botões centralizados.
- Os volumes são salvos numa pasta escolhida, nunca na pasta de origem; um aviso aparece quando a origem e os volumes estão no mesmo disco.
- Durante a compactação o upload fica limitado a 1 MB/s (ajustável em Configurações).
- Opção **Compactação e Upload avançados**: compactação e upload se alternam no disco, sem rodar juntos.
- Duplo clique numa pasta do Drive também a escolhe como destino.
- Painéis do computador e do Drive divididos meio a meio; coluna do nome do tamanho do texto, barras maiores e centralizadas.
- Barra concluída em azul esverdeado.
- Novo tema **Grafite e verde** (temas Spotify, Verde escuro e Cinza grafite antigos abrem nele).
- Atualizar no Drive recarrega todas as pastas abertas.
- Árvores mantêm a hierarquia: abrir uma pasta não desloca a lista nem troca a raiz.
- Aviso na tela quando já existe no destino do Drive um arquivo com o mesmo nome; o Compactar confere os nomes dos volumes antes de começar.
- Pastas podem ser marcadas: Iniciar envia a pasta com as subpastas recriadas no Drive; Compactar usa a pasta marcada como origem e nome.

## Desktop v1.3.0 — 10/10/2026

- Botão **Entrar com Google**: o cliente OAuth vai embutido na compilação e não é mais preciso selecionar o JSON a cada conexão. Importar outro JSON continua em Configurações.
- Acesso a todas as pastas do Drive passa a ser o padrão no login.
- Novo visual no padrão Nexotool: janela sem a barra do Windows, cabeçalho e rodapé azul-marinho, faixa azul-ciano, cartões e botões redesenhados.
- Tema Automático, Claro ou Escuro. Temas escuros anteriores abrem no Escuro.
- Símbolos do Google Drive e do Gmail, e ícones novos para Voltar, Atualizar e Nova pasta.
- Cerca de 50 textos encurtados ou removidos.
- Motor de upload, retomada, fila e atualizador permanecem inalterados.

## Desktop v1.2.0 — 07/10/2026

- Consulta automática da pasta aberta e destino do Drive a cada 30 segundos, sem sobreposição de consultas.
- Falhas de consultas automáticas são registradas sem interromper o usuário com diálogos.
- Verificação de releases estáveis do desktop na abertura e a cada seis horas, além do botão em Configurações.
- Download em segundo plano com tamanho e SHA-256 verificados contra a release oficial.
- Instalação pela interface, após pausar uploads, com teste de inicialização, cópia da versão anterior e reinício.
- Credenciais e fila são preservadas. A instalação inicial desta versão é manual.
- Inclui a correção da atualização pendente descrita na versão 1.1.1.

## Desktop v1.1.1 — 07/10/2026

- Corrige perda de atualização da pasta do Drive quando a conclusão de um upload
  pede uma recarga durante uma consulta que falha. A recarga pendente agora também
  é executada após erro, atualizando o tamanho exibido sem reabrir o aplicativo.
- Respostas antigas não interferem após troca de conta ou reconstrução da árvore.
- A repetição consome somente a solicitação pendente, sem ciclo infinito de tentativas.
- Motor de upload, retomada, autenticação e Android permanecem inalterados.

## Desktop v1.1.0 — 21/09/2026

- Executável portátil inclui as dependências de monitoramento Firebase e QR code.
- Telemetria opcional no Firestore, independente do OAuth e do upload ao Drive.
- Pareamento por QR de uso único com validade de cinco minutos e revogação de acesso.
- Compatível com Android Monitor 0.2.2 e Firebase Spark, sem notificações push.
- Preserva configurações, credenciais e fila locais da versão anterior.
- Smoke test valida Firestore/gRPC e QR sem rede.

## Android Monitor v0.2.2 — 21/09/2026

- Monitoramento de várias máquinas por pareamento via QR code de uso único.
- Consulta do estado atual dos uploads, progresso, velocidade, fila e destino pelo Firestore.
- Compatibilidade com o plano Firebase Spark, sem notificações push nesta versão.
- Quatro temas iguais aos do Windows e logo fixo no topo das telas.
- Título Drive Flow centralizado apenas na tela inicial e ícone original de upload.
- Abas Computadores e Configurações, com textos centralizados sob os ícones.
- Aparência e atualização da conexão reunidas em Configurações; scanner na tela inicial.
- Ícone Android derivado de upload.ico e solicitação de atalho na primeira abertura,
  mediante confirmação do Android; opção para repetir em Configurações.
- APK de distribuição manual, assinado com a chave de depuração usada nas versões anteriores.

As versões Android são independentes das versões do software Windows.
Notas completas: [Android v0.2.2](docs/releases/android-v0.2.2.md).

## v1.0.5 — 20/09/2026

- Falhas temporárias de autenticação, inclusive durante o upload, passam pelo mecanismo de tentativas e preservam o progresso.
- Renovação de credenciais sincronizada entre uploads e navegação de pastas, com gravação das credenciais renovadas e recuperação de HTTP 401.
- Recusas definitivas da autorização impedem iniciar os próximos uploads até reconectar; credenciais locais e fila são preservadas.
- Consulta após expiração da sessão de upload também recupera falhas temporárias, sem reiniciar o envio do zero automaticamente.
- Diagnósticos incluem etapa, tipo de erro e progresso; horário do último bloco confirmado fica salvo. Tokens e URLs de sessão não são registrados.
- Pausa durante a espera por autenticação interrompe a espera e mantém os próximos itens pausados. O limite configurado de tentativas permanece vigente.

## v1.0.4 — 20/09/2026

- Pausar um upload também pausa os itens aguardando, evitando iniciar o próximo automaticamente. Outros uploads já ativos continuam.
- Pasta de destino e caminho em verde, preservados ao navegar e atualizar a árvore.
- Conta restaurada sem consulta de rede após salvar sua identificação; migração automática das credenciais antigas após consulta bem-sucedida.
- Falhas temporárias preservam a credencial; nova tentativa usa a autorização salva. Revogação pelo Google recebe diagnóstico específico.
- Credenciais continuam cifradas pelo Windows em `%LOCALAPPDATA%\DriveFlow`, fora da pasta do executável, compartilhadas entre versões.

## v1.0.3 — 20/09/2026

- Controles da fila em um único grupo, com separação maior antes de remover.
- Fundos dos controles e progresso transparentes, respeitando a cor da linha.
- Coluna de controles ampliada e margem direita para preservar a borda do botão remover.

## v1.0.2 — 20/09/2026

- Alinhamento vertical explícito do indicador de conexão, status e botão de conectar.

## v1.0.1 — 20/09/2026

- Árvore de pastas e arquivos do Drive com ícones do Windows e atualização após uploads.
- Caminhos sem espaços ao redor de `/`, indicador discreto de conexão e checkbox visível.
- Nova tentativa de autenticação liberada mesmo quando outras operações estão pendentes.
- Gráficos por upload simultâneo, com janela de 2 minutos e cores do tema.
- Tempo decorrido persistido (exclui pausas) e restante estimado pela velocidade do último bloco.
- Play, pause, stop e remoção individual com confirmação e parada segura; rodapé antigo removido.
- Ícone na barra de tarefas e barra de progresso animada até o valor confirmado.
- Executável portátil único com bibliotecas incluídas e versão nas propriedades do Windows.

## v1.0.0

- Versão inicial: uploads retomáveis, fila persistente, OAuth, temas e inicialização com Windows.

## Política de versão

Cada nova entrega deve alterar `driveflow/version.py` e adicionar uma entrada aqui antes de compilar.
Correções incrementam PATCH (v1.0.2); novas funcionalidades incrementam MINOR (v1.1.0);
mudanças incompatíveis incrementam MAJOR (v2.0.0). O título, a barra lateral, o executável
portátil e as propriedades do Windows usam essa mesma fonte de versão.
