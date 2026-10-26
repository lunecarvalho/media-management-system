# MediaTrack no Render — aplicação publicada

**Aplicação online:** [MediaTrack](https://media-track-w5xm.onrender.com).
Hospedagem: Render Free, com Docker, Django, Gunicorn e PostgreSQL 18.
Entrega acadêmica: **06/11/2026**.

O endereço é público e permite visualizar a tela de login. As páginas internas,
a API e as funções administrativas exigem autenticação e permissões, conforme a
[política de acesso](architecture.md#permissões). Credenciais não são divulgadas.
O primeiro acesso após inatividade pode levar cerca de um minuto para reativar
o serviço no plano gratuito; veja os [limites oficiais](https://render.com/docs/free).
Para instalação e execução local, consulte [DEVELOPMENT.md](../DEVELOPMENT.md).

## Estrutura reutilizada

Django/DRF, modelos, migrações, Gunicorn, Dockerfile, WhiteNoise e endpoints de
saúde continuam iguais em funcionalidade. `config.settings` mantém SQLite para
desenvolvimento. `config.production` e workflows AWS foram preservados.
`config.render` importa as configurações comuns e aplica validações próprias.
Não há dependência de SDK AWS para servir a aplicação.

O Dockerfile mantém collectstatic com `config.static_settings`, sem banco/secrets
ou migrações no build, e usuário não privilegiado. Gunicorn aceita PORT, com
fallback 8000 para os usos existentes. A configuração Render sobrescreve o comando
de início para executar migrações antes de iniciar Gunicorn na porta da plataforma.
`.dockerignore` já exclui .env, credenciais, bancos SQLite, backups e datasets.
WhiteNoise serve somente estáticos; disco efêmero não serve para persistir uploads.
Os datasets excluídos precisam de importação planejada se a funcionalidade os exigir.

## Configuração e segurança

| Variável | Configuração/uso |
| --- | --- |
| DJANGO_SETTINGS_MODULE | `config.render` |
| DEBUG | `False` obrigatório |
| SECRET_KEY | Secret exclusivo, aleatório, pelo menos 50 caracteres; nunca versionar |
| DATABASE_URL | URL interna do PostgreSQL Render, mesma região do web; manter somente no ambiente seguro |
| ALLOWED_HOSTS | Host público exato, sem esquema/wildcard; separar hosts por vírgula |
| CSRF_TRUSTED_ORIGINS | Origem HTTPS exata correspondente aos hosts autorizados, sem barra final ou caminho |
| PORT | Fornecida pelo Render; não precisa de valor manual |
| CORS_ALLOWED_ORIGINS | Opcional; vazio se não houver frontend de outra origem |
| MUSICBRAINZ_USER_AGENT | Opcional; identificação pública apropriada da aplicação |

Não há fallback para SQLite em `config.render`. Sem DATABASE_URL o runtime
falha de forma fechada; build de estáticos continua independente. Nunca publicar
valores de secrets ou URLs privadas do banco na documentação ou no repositório.

HTTPS é obrigatório, cookies de sessão/CSRF permanecem seguros, CSRF middleware
permanece ativo. Render usa X-Forwarded-Proto; a configuração confia nesse proxy
quando executada atrás do Render. Não publicar diretamente esse container com
headers de proxy arbitrários. AWS conserva sua configuração CloudFront existente.
`/health/` pode usar HTTP para sondagem interna e não consulta banco; `/readiness/`
permanece HTTPS, executa SELECT 1 e responde 503 sem expor detalhes se o banco falhar.
Conferir também o Host utilizado pelas sondagens após mudanças de configuração; não
contornar falhas ampliando ALLOWED_HOSTS para wildcard.

## PostgreSQL e TLS

A conexão interna Render usa certificados autoassinados, sem suporte a verify-full.
Somente `config.render` define sslmode=require se a URL não especificar modo:
criptografa o tráfego, mas não autentica CA/hostname como verify-full. Essa diferença
é explícita, não deve ser aplicada ao RDS. Modos disable/allow/prefer são rejeitados.
verify-full continua permitido quando houver endpoint e CA compatíveis, exigindo
sslrootcert. connect_timeout é limitado a 1–30s, padrão 5s.

Manter a conexão interna de banco na mesma região, restringir/desativar acesso
externo quando não necessário e validar TLS real e readiness. Não consultar nem
publicar secrets nos logs. Quando usar acesso externo autorizado para exportação,
restringir IPs, usar TLS e remover a liberação depois. Testes automatizados devem
usar bancos exclusivos de teste, nunca a URL de produção.

## Blueprint e migrações no Free

`render.yaml` descreve somente **um web service Free**; não contém seção databases,
discos, jobs ou planos pagos. DATABASE_URL e secrets exigem configuração manual
(`sync: false`). O arquivo mantém auto-deploy desligado e não gerencia o banco
existente. A região está omitida no YAML: em qualquer recriação, preservar a mesma
região do banco (Ohio, US East). Para o serviço já publicado, conferir as
configurações no painel; não aplicar um novo Blueprint para recriá-lo.

Free não possui pre-deploy command, shell ou one-off jobs. O Docker Command
é `/bin/sh /app/scripts/start-render.sh`, sem aspas externas. O script POSIX
`scripts/start-render.sh` executa migrações e, somente em caso de sucesso, substitui
o shell pelo Gunicorn com `exec`. Usa PORT do Render, com fallback 10000.
Isso evita problemas de interpretação das aspas do comando composto no painel.
O Dockerfile já inclui o script via `COPY . .`; a chamada explícita de `/bin/sh`
dispensa permissão executável. `.gitattributes` mantém o script com finais LF.
Manter `DJANGO_SETTINGS_MODULE=config.render` no ambiente do serviço, pois o
Dockerfile conserva `config.production` como padrão para os usos existentes.
Migrações rodam no início do container, com acesso ao banco em runtime. Se falham,
Gunicorn não inicia. Não rodam no build, nem no startup AWS padrão.

Esse procedimento reaplica o comando em reinícios; Django só aplica migrações
pendentes. É adequado ao protótipo com uma instância e deploys manuais serializados.
Não disparar múltiplos serviços/deploys contra o mesmo banco. Durante atualização,
versão anterior pode continuar atendendo: só usar migrações compatíveis ou janela
controlada. Não há rollback automático de schema; a migração Produto/Exemplar é
intencionalmente irreversível. Migrações grandes podem exceder o prazo de startup.
Se isso ocorrer, parar e planejar execução controlada externa, não repetir cegamente.

## Primeiro administrador no Render Free (procedimento temporário)

As credenciais locais não são copiadas para o PostgreSQL de produção. Para um
serviço já funcionando e com migrações aplicadas, use o procedimento abaixo
somente depois de publicar os arquivos revisados no repositório usado pelo Render.
Não é necessário Shell interativo, job pago ou alteração do Dockerfile.

1. Em Environment do serviço, configure `DJANGO_SUPERUSER_USERNAME`,
   `DJANGO_SUPERUSER_EMAIL` e `DJANGO_SUPERUSER_PASSWORD`. Use uma senha forte,
   exclusiva e armazenada no gerenciador de senhas. Não use argumentos de comando,
   arquivos versionados, prints ou capturas dessas variáveis.
2. Troque temporariamente Docker Command para
   `/bin/sh /app/scripts/bootstrap-render-admin.sh`, sem aspas externas.
   Preserve `DJANGO_SETTINGS_MODULE=config.render` e as demais variáveis.
   Aplique as mudanças em uma única inicialização/deploy manual, sem execuções
   concorrentes. Esse deploy é necessário para executar o comando no plano Free.
3. O comando `bootstrap_render_admin` chama o `createsuperuser` nativo em modo
   não interativo, usando somente as variáveis acima. Valida a senha antes de criar
   o usuário, pois o modo não interativo nativo não executa esses validadores.
   Os logs indicam sucesso, ausência de alterações ou erro genérico, sem senha.
   Depois, o script remove essas variáveis do ambiente herdado pelo Gunicorn e
   inicia o script normal `start-render.sh`, sem modificá-lo.
4. Confirme o acesso a `/admin/`. O superusuário não precisa de Perfil para esse
   acesso. Se já existir qualquer superusuário, o provisionamento não cria outro
   nem altera senha, e-mail ou permissões. Se o nome pertencer a usuário comum,
   o comando falha sem promovê-lo. Falhas impedem o início do servidor nesse modo
   temporário; para restabelecer o serviço, retorne ao comando normal.
5. Retorne Docker Command a `/bin/sh /app/scripts/start-render.sh` e **exclua as
   três variáveis `DJANGO_SUPERUSER_*` do painel Render**. Aplique a limpeza e
   reinicialização/deploy. A conta permanece no PostgreSQL; a senha não é redefinida.

O comando normal e o `render.yaml` não acionam o provisionamento. Se houver um
reinício antes da limpeza, a presença de superusuário torna a execução inócua.
Esse procedimento cria apenas o primeiro administrador; não recupera senhas de
contas existentes. Não habilite logs DEBUG de SQL durante o provisionamento.

## Conta de avaliador acadêmico

O perfil `Avaliador` é um `Perfil` Django ativo, sem `is_staff` e sem
`is_superuser`. Ele recebe apenas `consultar` e `editar_acervo`: isso permite
testar o dashboard, consultas, movimentações, cadastro/edição do acervo,
pesquisa de metadados e os endpoints de leitura/escrita do acervo. Não recebe
`excluir_acervo`, `categorias` ou `usuarios`; portanto não gerencia contas,
grupos, permissões, configurações administrativas, categorias ou exclusões.
`AcessoInternoMiddleware` e `AcessoAPI` usam a mesma política, inclusive para
requisições diretas à API. O perfil equivalente no formulário interno é
propositalmente mantido, mas a conta abaixo deve ser criada pelo comando
controlado.

O provisionamento não é executado pelo deploy normal. Para criar a conta uma
única vez no PostgreSQL de produção, depois de publicar os arquivos revisados:

1. No Environment do web service Render, configure temporariamente
   `DJANGO_EVALUATOR_USERNAME`, `DJANGO_EVALUATOR_EMAIL` e
   `DJANGO_EVALUATOR_PASSWORD`. Gere uma senha exclusiva, forte e armazenada no
   gerenciador de senhas; não a coloque em comandos, arquivos, prints ou logs.
2. Altere temporariamente Docker Command para
   `/bin/sh /app/scripts/bootstrap-render-evaluator.sh`, sem aspas externas.
   Preserve `DJANGO_SETTINGS_MODULE=config.render`, `DATABASE_URL` e as demais
   variáveis. Faça somente um deploy/reinício manual e não execute duas
   inicializações concorrentes.
3. O comando `bootstrap_render_evaluator` lê somente as três variáveis,
   valida a senha, cria o usuário com perfil `avaliador` em uma transação e
   força `is_staff=False` e `is_superuser=False`. O script remove as variáveis
   antes de iniciar o Gunicorn chamando `scripts/start-render.sh`.
4. Confirme o login e teste `/`, `/acervo/`, `/movimentacoes/` e `/api/`. A
   execução repetida para o mesmo avaliador seguro é inócua: não troca senha,
   e-mail ou permissões. Se o nome já pertencer a outra conta, o comando falha
   sem promovê-la nem alterá-la.
5. Após confirmar a criação, retorne Docker Command para
   `/bin/sh /app/scripts/start-render.sh`, remova as três variáveis
   `DJANGO_EVALUATOR_*` do painel Render e reinicie/deploye novamente. O script
   de bootstrap permanece versionado, mas não é público nem chamado pelo
   startup normal; o mecanismo temporário fica desativado pela restauração do
   comando e pela remoção das variáveis.

Esse procedimento não acessa diretamente dados de produção, não cria endpoint
público, não redefine contas existentes e não altera o PostgreSQL além do novo
usuário e seu perfil. Não use o comando normal para provisionar e não inclua
credenciais em `render.yaml`.

## Operação e limites do plano gratuito

- Após atualizações, conferir `/health/`, `/readiness/`, login, permissões,
  estáticos e persistência. `/health/` não consulta o banco; não substitui readiness.
- Manter exportações lógicas independentes e testar restauração antes de mudanças
  nos dados. PostgreSQL Free tem limite de 1 GB, não possui backups gerenciados e
  expira 30 dias após a criação. Conferir a data exata no painel para garantir a
  entrega de 06/11/2026; a carência não mantém o banco acessível.
- Abrir a aplicação antes da apresentação para acomodar a reativação após
  inatividade. Monitorar horas, tráfego e builds conforme os limites do plano.
- Disco do container é efêmero; não depender dele para uploads ou dados persistentes.
  A importação da base de DVDs é separada do deploy, conforme o [guia de dados](data-import.md).
- Revisar código e migrações antes de deploys manuais, sem execuções concorrentes.
  Não há rollback automático do schema.

## Histórico de preparação e AWS

A preparação local anterior à publicação validou configurações Render, TLS,
proxy, CSRF, probes e testes com bancos temporários. Naquela etapa não houve
conexão ao Render nem build Docker local; essas limitações são históricas e não
indicam que a aplicação atual esteja aguardando seu primeiro deploy.

Os [registros AWS](archive/aws.md) permanecem arquivados e não são instruções
vigentes para o Render. A publicação no Render não comprova a desativação de
recursos AWS; qualquer operação nesses recursos deve ser tratada separadamente.

## Referências

- https://render.com/docs/free
- https://render.com/docs/deploys
- https://render.com/docs/docker
- https://render.com/docs/postgresql-creating-connecting
- https://render.com/docs/blueprint-spec
