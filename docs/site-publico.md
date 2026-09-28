# Página pública do DriveFlow

Arquivos estáticos em `site/`, sem dependências de compilação. O workflow
`.github/workflows/pages.yml` publica somente essa pasta, nunca `dist/` ou credenciais.

## Publicar

Em GitHub → Settings → Pages → Build and deployment, selecione GitHub Actions.
Faça commit dos arquivos do site e workflow e envie para `main`. Acompanhe a execução
na aba Actions. O endereço esperado é https://gustavotoigo-max.github.io/DriveFlow/.

## Conferir localmente

Execute `python -m http.server 8080 --directory site` na raiz e abra http://localhost:8080.
Confira página inicial, privacidade, termos e links de navegação no desktop e celular.

## Google OAuth

Após a publicação e confirmação de que todas as páginas abrem, use:

- Página inicial: https://gustavotoigo-max.github.io/DriveFlow/
- Privacidade: https://gustavotoigo-max.github.io/DriveFlow/privacidade.html
- Termos: https://gustavotoigo-max.github.io/DriveFlow/termos.html

A publicação dessas páginas não garante aprovação do Google. Se for solicitada prova
 de propriedade, use a verificação de prefixo de URL no Search Console com o arquivo
ou meta tag fornecido pelo Google. Não invente o token de verificação. O domínio
candidato é `gustavotoigo-max.github.io`; não declare propriedade sobre `github.io`.
Se o console não aceitar esse subdomínio, será necessário um domínio próprio.

Referência: https://support.google.com/cloud/answer/15549049?hl=pt-BR

O responsável e contato são Gustavo Toigo e gustavo.toigo@gmail.com, já usados no
branding OAuth. Atualize a política quando mudar o tratamento de dados do aplicativo.
