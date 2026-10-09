# Entrar com Google

A partir da versão 1.3.0 o executável pode trazer o cliente OAuth embutido. Quem usa o
DriveFlow clica em **Entrar com Google**, escolhe a conta no navegador e autoriza o acesso
ao Drive. Não é preciso selecionar nenhum JSON.

O Google exige que a autorização aconteça no navegador do sistema; janelas de login dentro
do aplicativo são bloqueadas por ele. A senha nunca passa pelo DriveFlow.

## 1. Preparar o projeto no Google Cloud (uma vez)

1. Abra o [Google Cloud Console](https://console.cloud.google.com/) e selecione o projeto já usado pelo DriveFlow.
2. Em **APIs e serviços → Biblioteca**, confirme que a **Google Drive API** está ativada.
3. Em **Google Auth Platform → Clientes**, use o cliente do tipo **Aplicativo para computador**
   (ou crie um) e baixe o JSON.

## 2. Publicar o app em produção (acaba com a expiração de 7 dias)

Projetos externos em modo **Teste** têm autorizações do Drive que expiram em 7 dias.
Para contas `@gmail.com` não existe o tipo Interno, então o caminho é publicar:

1. Em **Google Auth Platform → Público-alvo**, clique em **Publicar app** e confirme.
2. Em **Branding**, preencha nome do app, e-mail de suporte e e-mail do desenvolvedor.
   Não é necessário enviar o app para verificação para uso interno.
3. Depois de publicar, **desconecte e entre novamente** no DriveFlow em cada computador.
   Autorizações obtidas no modo Teste continuam expirando; só as novas ficam válidas.

Sem verificação o app funciona para até 100 contas. No primeiro login o Google mostra
**"O Google não verificou este app"**: clique em **Avançado → Acessar DriveFlow (não seguro)**
e autorize. Isso aparece apenas na autorização, não nos uploads.

A autorização ainda pode ser encerrada se o acesso for removido em [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
ou se ficar 6 meses sem uso. Nesses casos basta entrar novamente; a fila é preservada.

Para vender o DriveFlow a terceiros, o acesso a todas as pastas (escopo `drive`) exige a
verificação do Google com avaliação de segurança anual paga.

## 3. Compilar com o cliente embutido

1. Copie o JSON baixado para `driveflow\oauth_client.json`.
   O nome está no `.gitignore`: **nunca faça commit desse arquivo**, o repositório é público.
2. Execute `Compilar.bat`. Se o arquivo estiver ausente, a compilação avisa e o executável
   volta a pedir o JSON ao conectar.

Ao rodar pelo código-fonte (`Iniciar.bat`), o mesmo arquivo em `driveflow\oauth_client.json`
ativa o botão.

## Outro cliente OAuth

Em **Configurações → Conexão e armazenamento local**, **Entrar com cliente OAuth próprio (JSON)…**
continua aceitando um JSON de outro projeto. Desconecte a conta atual antes.

## Permissão de acesso

O login pede acesso a todo o Drive por padrão, para navegar pelas pastas já existentes.
Para restringir aos arquivos criados pelo DriveFlow, desmarque **Acessar pastas existentes
de todo o Drive** em Configurações, salve e entre novamente.
