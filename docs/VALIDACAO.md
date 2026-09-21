# Validação local — DriveFlow

Versão: v1.0.1. Data: 20/09/2026. Ambiente: Windows x64, Python 3.14.2, PySide6 6.11.2.

## Testes automatizados

Comando: `.venv\Scripts\python.exe -m pytest -q`.

Resultado: **36 testes aprovados**.

- Perda da resposta de um bloco já aceito: consulta remota e continuação no offset correto.
- Pausa e reabertura do SQLite: reconciliação de checkpoint local divergente, sem nova sessão.
- Perda da resposta final: recuperação pelo ID pré-alocado, sem novo upload.
- Alteração de arquivo: bloqueio de retomada.
- Arquivo indisponível: preservação da sessão e retomada quando retorna.
- Sessão expirada: preservação do progresso, sem reenvio automático.
- Tamanho remoto divergente: não marca conclusão.
- Nome remoto duplicado: bloqueia início.
- Limite de retries: mantém sessão e progresso.
- Outra conta: não inicia upload.
- Mesmo nome em origens diferentes: bloqueia duplicidade na fila do mesmo destino.
- Cancelamento de sessão expirada: mantém estado terminal.
- Protocolo HTTP: Content-Range, Range e desativação de redirecionamento de 308.
- URLs de sessão fora do endpoint esperado: três casos rejeitados.
- DPAPI: cifragem e decifragem real no Windows.
- Arquivo esparso de 100 GiB: offset de 64 bits e leitura de apenas 256 KiB finais.
- Interface: seleção entre pastas, fila, configuração de tema e renderização.
- Autenticação: permissões adicionais já concedidas, rejeição de permissões ausentes, preservação de avisos inesperados, dois formatos de erro de API desativada, ausência de confirmação prematura no navegador e mensagens sem segredos.
- Inicialização: registro para o usuário atual, caminhos com espaços e remoção apenas da entrada DriveFlow, usando Registro simulado nos testes.
- Interface atualizada: status sem sobreposição, imagem da marca carregada, ícone de disco e opção de início com o Windows.
- Fluxo de envio: um clique adiciona os arquivos selecionados e inicia apenas os itens marcados; desmarcar pausa, remarcar não inicia automaticamente.
- Agendamento: itens desmarcados não são iniciados, mesmo com estado aguardando.
- Migração: filas anteriores preservam sessões/progresso e recebem a marcação padrão; escolhas posteriores persistem ao reabrir.
- Progresso animado: a barra não ultrapassa os bytes confirmados, não reinicia a animação sem novo progresso e aplica correções/trocas de arquivo imediatamente.

- Remoção ativa: sinaliza pausa, preserva o registro enquanto o worker opera e remove somente após terminar.
- Tempo decorrido: soma tempo ativo ao valor persistido.
- Árvore: arquivos dentro das pastas, inclusão após atualização, preservação da expansão e rejeição de resposta de conta anterior.
- Falha de autenticação: libera nova conexão mesmo com consulta de pastas pendente.
- Gráficos: dois uploads simultâneos, amostras limitadas e renderização nos quatro temas; imagem em `graficos.png`.

## Revisão visual

A renderização da janela real PySide6 está em `interface.png`. Foram conferidos contraste, legibilidade, organização das áreas e bordas discretas. O ambiente de teste carrega explicitamente as fontes Segoe UI para o plugin Qt offscreen.

O tema Spotify e a faixa compacta de indicadores estão em `interface-spotify.png`, com dois arquivos fictícios de teste para demonstrar a fila marcada/desmarcada.

## Ainda depende da conta Google

Não foram executados OAuth com uma conta real, uploads reais ao Google, reinicialização real do Windows durante envio, remoção física de HD durante envio ou transferência real de 100 GiB. Esses testes exigem credencial OAuth, autorização e arquivos de teste do usuário. Os testes locais validam o comportamento da implementação com respostas simuladas, sem substituir essa homologação.

## Distribuição Windows

O empacotamento foi ajustado em `DriveFlow.spec` para impedir a inclusão de uma DLL ICU de terceiros encontrada no PATH; o Qt utiliza a biblioteca do sistema Windows. O teste `--smoke-test` abre as cinco páginas da estrutura da interface em modo offscreen, em diretório temporário isolado, e produz um JSON de sucesso antes de encerrar. Ele não acessa credenciais do usuário nem envia arquivos.


### Pacotes v1.0.1

- `dist/DriveFlow/DriveFlow.exe`: smoke test com saída 0; cinco páginas, ícone e assets presentes (`smoke-v1.0.1-folder.json`).
- `dist/DriveFlow-v1.0.1-portatil.exe`: 71.712.941 bytes, versão Windows 1.0.1. Copiado sozinho para uma pasta isolada; executado com PATH restrito ao Windows/System32, sem Python/Qt de desenvolvimento no PATH. Smoke test com saída 0 e assets presentes (`smoke-v1.0.1-portable.json`).
- Os dois testes usam dados temporários, sem modificar a conta, a fila real ou o registro de inicialização.
- Não foi executado em um segundo computador físico; esta validação comprova o empacotamento isolado no Windows deste ambiente.


## Ajuste visual v1.0.3

Três testes existentes de interface passaram. A inspeção adicional validou os quatro temas na largura mínima de 1080 pixels lógicos e escala de 150%: os quatro botões permanecem dentro do grupo e da área visível da tabela, com separação maior antes do X. Renderização em `controls-v1.0.3-150pct.png`. Controles e progresso agora respeitam o fundo da linha, sem blocos opacos. O aplicativo v1.0.2 aberto pelo usuário não foi interrompido.
