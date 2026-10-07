# DriveFlow Desktop 1.2.0 — Windows

Atualização automática das pastas e atualização do próprio aplicativo pela interface.
Compatível com o [Android Monitor 0.2.2](https://github.com/gustavotoigo-max/DriveFlow/releases/tag/android-v0.2.2), sem necessidade de atualizar o APK.

## Novidades

- A pasta aberta e o destino selecionado no Google Drive são consultados a cada 30 segundos, sem sobreposição de consultas ou avisos repetidos em falhas de rede.
- Os arquivos locais continuam usando o monitoramento de alterações do Windows. Isso não cria nem reenvia uploads automaticamente.
- Corrigida a perda de atualização pendente quando uma consulta à pasta falhava durante a conclusão do último upload.
- Configurações inclui verificação de releases estáveis, download com progresso e instalação com reinício.
- O executável verifica atualizações na abertura e a cada seis horas; download e instalação dependem da ação do usuário.
- A integridade é conferida por tamanho e SHA-256. Antes da substituição, a nova versão passa por um teste de abertura. O executável anterior é mantido como backup.

## Como atualizar agora

1. Pause os uploads e feche a versão anterior.
2. Baixe `DriveFlow-v1.2.0-portatil.exe` nos anexos. Ele contém todas as bibliotecas necessárias.
3. Coloque-o em uma pasta definitiva e abra-o usando o mesmo usuário Windows. A fila e as configurações em `%LOCALAPPDATA%/DriveFlow` serão preservadas.
4. Se utiliza a instalação existente, substitua o `DriveFlow.exe` da pasta do programa pelo novo portátil, renomeando a cópia para `DriveFlow.exe`, para manter os atalhos existentes.
5. Confira a versão 1.2.0 e retome os uploads desejados.

Esta primeira atualização é manual porque as versões anteriores não têm o atualizador.
Nas próximas releases, use Configurações → Verificar atualizações → Baixar atualização.
Pause os uploads, aguarde as operações terminarem e escolha Instalar e reiniciar.

Windows 10/11 x64. Executável portátil sem assinatura Authenticode. Credenciais, JSONs e instalador privado não fazem parte desta release. Nenhuma mudança no OAuth do Drive ou no pareamento Firebase é necessária.

## Validação

- 80 testes automatizados aprovados.
- Troca de executáveis testada isoladamente em três cenários: sucesso, falha de abertura e checksum inválido.
- Portátil validado em pasta temporária, com interface, ícones, Firebase/QR e auxiliar de atualização presentes.
- Os testes não acessaram credenciais reais nem enviaram arquivos ao Google Drive.

[Guia do atualizador e recuperação](https://github.com/gustavotoigo-max/DriveFlow/blob/v1.2.0/docs/atualizacoes.md).
