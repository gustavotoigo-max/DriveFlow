# DriveFlow Desktop 1.1.0 — Windows

Executável portátil com monitoramento Firebase e pareamento por QR code para
acompanhar uploads no celular. Compatível com o
[DriveFlow Monitor Android 0.2.2](https://github.com/gustavotoigo-max/DriveFlow/releases/tag/android-v0.2.2).

## Novidades

- Publicação opcional do estado atual de cada computador no Firestore.
- Progresso consolidado em intervalos configuráveis, com mudanças de estado prioritárias.
- Monitoramento em segundo plano, independente da autenticação e dos uploads ao Drive.
- Pareamento de uma ou mais máquinas no Android usando códigos de uso único, válidos por cinco minutos.
- Revogação do acesso de celulares nas configurações do desktop.
- Dependências Firebase, gRPC e QR incluídas no executável; não exige Python instalado.
- Compatível com Firebase Spark, sem notificações push nesta entrega.

## Instalação e atualização

1. Baixe `DriveFlow-v1.1.0-portatil.exe` nos anexos.
2. Feche a versão antiga e coloque o novo executável em uma pasta definitiva.
3. Abra o novo executável. A fila, as configurações e a autenticação existentes
   são reutilizadas em `%LOCALAPPDATA%/DriveFlow` no mesmo usuário Windows.
4. Em Configurações, habilite o monitoramento e selecione sua credencial Firebase,
   caso ainda não esteja configurada. A credencial não está incluída no executável.
5. Instale o APK Android 0.2.2 e use Configurações → Conectar celular no desktop.

Windows 10/11 x64. O arquivo é portátil: não há instalador. A primeira abertura pode
levar alguns segundos para extrair as bibliotecas. O executável não possui assinatura
Authenticode; o Windows pode exibir um aviso de editor desconhecido.

O Android 0.2.2 permanece o mesmo APK, sem necessidade de reinstalar para esta atualização.
O guia de Firebase e pareamento está em
[docs/android-monitor.md](https://github.com/gustavotoigo-max/DriveFlow/blob/v1.1.0/docs/android-monitor.md).

## Validação

- 65 testes automatizados aprovados.
- Teste do executável portátil isolado: interface, ícones, versão e dependências Firestore/gRPC e QR.
- Testes de empacotamento não acessam credenciais reais nem executam uploads no Google Drive.
