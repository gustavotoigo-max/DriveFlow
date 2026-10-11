# DriveFlow Desktop 1.4.1 — Windows

Correção da atualização pela interface. Inclui tudo da [1.4.0](https://github.com/gustavotoigo-max/DriveFlow/releases/tag/v1.4.0): Compactar com o WinRAR, envio de pastas com subpastas e notificação no WhatsApp.

## Correção

- Ao atualizar pela interface, a nova versão podia fechar com "Failed to load Python DLL … _MEI…\python314.dll". Ela herdava a pasta temporária da versão anterior, que é apagada quando o app fecha. O atualizador agora inicia a nova versão sem essa herança.

## Como atualizar

- **Na 1.3.0 ou anterior (uma vez, manualmente)**: o atualizador dessas versões ainda tem o problema. Feche o DriveFlow, baixe `DriveFlow-v1.4.1-portatil.exe` e substitua o executável antigo, ou rode o instalador privado da 1.4.1.
- **Da 1.4.1 em diante**: Configurações → Verificar atualizações → Baixar atualização. O atualizador vai direto para a versão mais nova, mesmo pulando versões.

A fila, a conta e as configurações em `%LOCALAPPDATA%/DriveFlow` são preservadas.

Windows 10/11 x64. Executável portátil sem assinatura Authenticode.
