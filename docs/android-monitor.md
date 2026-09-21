# DriveFlow Monitor 0.2.2 — Spark, sem notificações

O Android está em `android/`, pacote `com.driveflow.monitor`, projeto Firebase
`update-driveflow`. Compatível com Android 8 ou superior, incluindo Galaxy M32.
APK: `dist/DriveFlow-Monitor-0.2.2-spark-debug.apk`.

## Interface 0.2.2

O ícone instalado usa a imagem extraída de `upload.ico`, em formato adaptativo para
Android. Na primeira abertura após instalar/atualizar, o app solicita ao launcher
um atalho na tela inicial. É necessário confirmar no diálogo do Android. A opção
Configurações → Adicionar à tela inicial permite repetir a solicitação; atalhos
já fixados pelo app não são duplicados. A colocação automática no instante da
instalação depende das configurações do launcher. Textos da barra inferior estão
centralizados sob os respectivos ícones.


Logo Datarestore fixo no topo de todas as telas. Título Drive Flow centralizado
apenas na tela inicial, acompanhado do ícone original de upload do Windows.
Abas Computadores e Configurações; a engrenagem reutiliza o recurso do Windows.
Aparência e Atualizar conexão ficam em Configurações. O scanner continua na tela inicial.

## Recursos desta versão

- Quatro temas do Windows: Azul profundo, Cinza grafite, Verde escuro e Spotify.
- Scanner de QR code, várias máquinas, lista e detalhes dos uploads.
- Progresso, velocidade, tamanho, estimativa, destino, fila e última atualização.
- Código de cinco minutos e uso único; revogação pelo Windows ou pelo celular.
- Identidade anônima por instalação, sem senha e sem chave privada no Android.
- Sem Firebase Messaging, permissão de notificações, Cloud Functions ou agendamento.
- As consultas em tempo real são desconectadas quando o app vai para o segundo plano.

## Ativar no projeto existente (sem mudar o Spark)

1. Em Firebase Authentication, habilite o provedor **Anônimo**.
2. Em Firestore → Regras (ou Google Cloud Firestore → Segurança), publique o conteúdo
   completo de `firebase/firestore.rules`. A cópia em `config/firestore.rules` é idêntica.
3. Abra o [desktop 1.1.0](https://github.com/gustavotoigo-max/DriveFlow/releases/tag/v1.1.0)
   ou o código atualizado (`Iniciar.bat`). O executável 1.1.0 inclui o QR de versão 2.
4. Instale o APK 0.2.2 no celular. Pode substituir a versão 0.1.0 de teste.
5. Windows → Configurações → Conectar celular. Mantenha o QR aberto durante o scan.
6. Android → Escanear QR code → confirme o computador.

As regras foram testadas localmente, mas ainda precisam ser publicadas no projeto
real. A autenticação anônima não foi ativada automaticamente. Não publique funções.
O plano Spark tem cotas de leitura/gravação compartilhadas pelo projeto: acompanhe
Uso no Firestore, especialmente com várias máquinas publicando a cada cinco segundos.

## Como o pareamento funciona sem servidor adicional

O Windows cria `pairing_codes/{sha256(token)}` usando sua conta de serviço.
O token tem 256 bits aleatórios. O QR versão 2 traz apenas esse token, projeto e
identificação da máquina; o documento inclui `protocol: spark-v2` e `expiresAt`.
A coleção de códigos não pode ser listada. Um celular autenticado que conheça o
hash imprevisível pode consultar somente esse código, enquanto ele estiver válido.
O hash também deve ser tratado como segredo temporário; não o publique nem o registre.

O Android faz uma transação que consome o código (`usedBy`, `usedAt`) e cria o
vínculo `readers/{uid}/computers/{id}` e seu espelho administrativo
`computers/{id}/readers/{uid}`. As Security Rules usam `getAfter` para exigir que
as três operações ocorram juntas, para a mesma máquina e identidade, com data do
servidor. Campos da autorização original não podem ser alterados pelo celular.

Dois celulares não podem usar o mesmo QR. Códigos vencidos e tentativas de criar
vínculo sem consumir um código são recusados. Depois da revogação, o código antigo
não recria o vínculo. Cada celular só pode consultar seus vínculos e as máquinas
explicitamente autorizadas. Não pode escrever telemetria nem listar todas as máquinas.
A leitura por outros clientes continua negada. O Windows mantém as permissões IAM.

Fechar o QR solicita sua exclusão. Se o programa terminar abruptamente, um documento
vencido pode permanecer, mas as regras negam seu uso. Não há serviço de limpeza pago.
Limpar os dados do Android ou reinstalar exige novo pareamento; backup/transferência
da identidade do app ficam desativados.

## Compilar e testar

Abra `android/` no Android Studio, sincronize e compile. JDK do Studio 25, Gradle
9.1.0, SDK 36.1 e Build Tools 36.1.0 foram utilizados. Baixe a configuração do seu app Android no Firebase e salve em
`android/app/google-services.json`. Esse arquivo local não acompanha o repositório.

```powershell
Set-Location android
.\gradlew.bat assembleDebug testDebugUnitTest lintDebug
```

Regras sem acesso ao projeto real (Node.js 22 e Java instalados):

```powershell
Set-Location firebase/functions
npm ci
npm run test:rules
```

Os testes usam apenas `demo-driveflow` no emulador local. Cobrem pareamento normal,
repetição, concorrência, vencimento, dados falsificados, transação parcial, acesso a
outras máquinas, escrita indevida, desvinculação e reaproveitamento de código revogado.

O código de notificações preparado anteriormente permanece em `firebase/functions`
para uma etapa futura, mas foi removido da configuração de implantação padrão.
O APK não contém os SDKs de Messaging/Functions nem executa chamadas a essas funções.
O monitor Windows não publica eventos de notificação nesta versão.

Referências: [transações e regras](https://firebase.google.com/docs/firestore/manage-data/transactions),
[condições de acesso](https://firebase.google.com/docs/firestore/security/rules-conditions),
[planos Firebase](https://firebase.google.com/docs/projects/billing/firebase-pricing-plans).
