# Notificações no WhatsApp

Quando todos os uploads de uma pasta de destino terminam, o DriveFlow manda uma mensagem no WhatsApp:

```
NOME DA PASTA UPLOAD FINALIZADO
```

O nome depende de como o envio foi feito:

- Arquivos marcados: o nome da pasta do Drive escolhida em **Usar esta pasta**. Exemplo: destino `Meu Drive/Clientes/Obra 12` gera `Obra 12 UPLOAD FINALIZADO`.
- Pasta marcada (envio com subpastas): o nome da pasta marcada. A mensagem sai uma vez, quando a pasta inteira termina.
- **Compactar**: o nome da pasta de origem. A mensagem sai quando o último volume termina de subir, depois que o WinRAR acaba.

O envio usa o [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/), que é gratuito e só manda mensagens para números que se ativaram nele.

## 1. Ativar cada número (uma vez, no celular)

Repita para cada pessoa que vai receber as mensagens.

1. Abra a página do CallMeBot para WhatsApp: <https://www.callmebot.com/blog/free-api-whatsapp-messages/>.
2. Salve nos contatos do celular o número do bot informado na página. Ele muda de tempos em tempos, então use sempre o que estiver lá.
3. Pelo WhatsApp, mande para esse contato a frase de autorização mostrada na página (em inglês, algo como `I allow callmebot to send me messages`).
4. Espere a resposta do bot. Ela traz a sua **apikey**, um número de alguns dígitos. Guarde-a.

Se a resposta não chegar em alguns minutos, mande a frase de novo.

## 2. Configurar no DriveFlow

1. Abra **Configurações** e role até **Notificações WhatsApp**.
2. No campo **Número**, digite o número com DDI e DDD, por exemplo `5511999998888`. Espaços, `+`, parênteses e traços são removidos sozinhos.
3. No campo **Apikey**, cole a apikey recebida do bot.
4. Clique em **Adicionar número**. O número aparece em **Números cadastrados**. Repita para outros números.
5. Clique em **Enviar teste**. Cada número deve receber `DriveFlow TESTE UPLOAD FINALIZADO`.
6. Marque **Enviar notificação ao finalizar upload** e clique em **Salvar notificações**.

Para tirar alguém, selecione o número em **Números cadastrados**, clique em **Remover selecionado** e depois em **Salvar notificações**. Para trocar a apikey de um número, adicione o mesmo número de novo com a apikey nova.

## Quando a mensagem é enviada

- A mensagem sai quando termina o último arquivo da pasta que ainda estava na fila (aguardando ou enviando). Vários arquivos para a mesma pasta geram uma única mensagem.
- Arquivos pausados não seguram o aviso. Se você pausar parte dos arquivos, o aviso sai quando os demais terminarem.
- Sem internet no momento da conclusão, a mensagem não é reenviada depois. O upload em si não é afetado.

## Onde ficam os dados

O número e a apikey ficam no banco local em `%LOCALAPPDATA%\DriveFlow`. A apikey é criptografada pelo Windows (DPAPI), igual ao token do Google. Nada disso vai para o repositório nem para o executável.

Cada envio, com ou sem erro, aparece na aba **Atividade** como `WHATSAPP_SENT` ou `WHATSAPP_ERROR`, mostrando só os quatro últimos dígitos do número.

## Problemas comuns

| Sintoma | O que fazer |
| --- | --- |
| O teste diz "CallMeBot recusou o envio" | Confira o número com DDI e a apikey. Se continuar, refaça a ativação no celular. |
| O teste diz "Sem conexão com o CallMeBot" | Verifique a internet ou se algum firewall bloqueia `api.callmebot.com`. |
| O teste deu certo, mas a mensagem não chegou | O CallMeBot às vezes atrasa alguns minutos. Se nunca chegar, refaça a ativação. |
