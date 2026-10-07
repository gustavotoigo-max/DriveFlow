# Pastas e atualização do aplicativo — Desktop 1.2.0

## Pastas

Arquivos locais usam o monitoramento nativo do QFileSystemModel/Windows. Na nuvem,
o aplicativo consulta a pasta aberta e a pasta marcada como destino a cada 30 segundos,
quando há conta conectada. A consulta usa as mesmas permissões existentes do Drive.
Não cria uploads, não altera arquivos nem reenvia automaticamente arquivos modificados.
Preserva seleção e pastas expandidas. Uma consulta pendente não se acumula com outra.
O botão Atualizar continua disponível. Falhas automáticas ficam na aba Atividade.

## Atualizar pela interface

1. Instale/abra o executável 1.2.0 uma vez manualmente: versões antigas não têm o atualizador.
2. Em Configurações, use Verificar atualizações. O executável também verifica sozinho
   após 20 segundos e a cada seis horas, sem baixar ou instalar automaticamente.
3. Havendo release estável mais recente, clique em Baixar atualização.
4. Pause os uploads e aguarde as operações em andamento terminarem.
5. Clique em Instalar e reiniciar e confirme. O aplicativo mantém a fila pausada.
6. Ao reabrir, confira a versão e retome os uploads desejados.

Há download, porém ele ocorre dentro do software. Não é atualização de código em
memória: o Windows exige reiniciar para trocar o executável. Funciona no portátil
ou na instalação por usuário, desde que haja permissão de gravação na pasta do executável.
Execuções pelo código-fonte apenas consultam versões.

## Contrato da release

Repositório fixo: `gustavotoigo-max/DriveFlow`. A release deve ser pública, não ser
rascunho/prerelease e ter tag `vMAJOR.MINOR.PATCH` e anexo exato
`DriveFlow-vMAJOR.MINOR.PATCH-portatil.exe`. O asset deve estar uploaded, ter tamanho
válido (até 300 MiB) e digest SHA-256 fornecido pela API GitHub. APKs, instaladores
privados e versões antigas são ignorados. Nunca publique JSONs ou instaladores com chaves.

O checksum detecta corrupção comparando com metadados obtidos por HTTPS do GitHub;
não substitui assinatura digital e não protege contra comprometimento da conta mantenedora.
Nenhum token Google ou Firebase é usado para consultar ou baixar releases.

## Recuperação e validação

Antes de substituir, o auxiliar valida o hash novamente e roda o smoke test do novo
executável sem dados reais. Aguarda o aplicativo encerrar; não encerra workers à força.
Usa substituição de arquivo com backup `.update-backup` ao lado do executável.
Se a validação ou troca falhar, conserva a versão anterior e tenta reabri-la. O teste
prévio não garante ausência de toda falha posterior durante o uso.
Logs ficam em `%LOCALAPPDATA%/DriveFlow/updates/download-*/result.txt`, exibidos na
área de atualização na próxima abertura. Downloads e backup ocupam espaço até remoção manual.
Se o PowerShell for bloqueado por política corporativa, a instalação automática pode falhar.
O instalador Windows pode continuar exibindo sua versão original na lista de aplicativos,
pois este mecanismo atualiza apenas o executável.

Testes: `.venv\Scripts\python.exe -m pytest -q` e
`.venv\Scripts\python.exe tools\check_update_helper.py` (somente Windows; executáveis fictícios).
