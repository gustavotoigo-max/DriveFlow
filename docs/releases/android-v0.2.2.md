# DriveFlow Monitor 0.2.2 — Android / Firebase Spark

Versão consolidada do aplicativo Android para acompanhar uploads do DriveFlow em
uma ou mais máquinas, pareadas pelo QR code gerado pelo software Windows.

Desktop compatível: [DriveFlow Windows 1.1.0](https://github.com/gustavotoigo-max/DriveFlow/releases/tag/v1.1.0).

## Recursos

- Monitoramento do arquivo atual, progresso, bytes enviados, velocidade, estimativa,
  destino, fila e última atualização.
- Pareamento por QR code de uso único, com validade de cinco minutos e revogação de acesso.
- Quatro temas do Windows: Azul profundo, Cinza grafite, Verde escuro e Spotify.
- Logo fixo no topo; título Drive Flow centralizado somente na tela inicial.
- Abas Computadores e Configurações, com textos alinhados ao centro dos ícones.
- Aparência e atualização da conexão em Configurações; scanner na tela inicial.
- Ícone do aplicativo baseado em upload.ico.
- Solicitação de atalho na tela inicial na primeira abertura, com confirmação do Android.
  A opção também está disponível em Configurações.

## Instalação e atualização

1. Baixe o arquivo `DriveFlow-Monitor-0.2.2-spark-debug.apk` nos anexos desta release.
2. Abra no celular e autorize a instalação por essa origem, se solicitado.
3. Para atualizar, instale por cima da versão anterior, sem desinstalar, preservando
   os computadores pareados. Isso exige a mesma assinatura do APK anterior.
4. Para uma instalação nova, gere o QR no Windows em Configurações → Conectar celular
   e use Escanear QR code no Android.

Requer Android 8 ou superior e Google Play Services para o scanner. O APK anexo está
configurado para o projeto Firebase usado nesta instalação do DriveFlow. Para usar
outro projeto, siga [o guia de configuração](../android-monitor.md) e compile seu APK.

## Escopo desta entrega

- Compatível com o plano Firebase Spark; sem notificações push.
- O monitoramento acompanha o estado enquanto o app está em primeiro plano.
- O APK usa assinatura de depuração para distribuição manual; esta entrega não é
  um pacote de publicação na Google Play.
- A release inclui o código do Windows com telemetria e pareamento. Os executáveis
  Windows v1.0.5 antigos não incluem o pareamento e não são anexados a esta release.
- Credenciais Firebase, OAuth, chaves de assinatura e configurações locais não
  acompanham o código-fonte.

## Validação

- Compilação Android e lint concluídos com sucesso.
- Interface, ícone e solicitação de atalho conferidos no emulador Android.
- Funcionamento no celular confirmado pelo usuário durante a consolidação da versão.
