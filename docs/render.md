# MediaTrack no Render — Fase 1, preparação local

Entrega acadêmica: **06/11/2026**. Nenhum serviço ou banco foi criado nesta fase.
Não houve deploy, migração de produção, commit, push ou alteração AWS.

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

| Variável | Valor/uso futuro |
| --- | --- |
| DJANGO_SETTINGS_MODULE | `config.render` |
| DEBUG | `False` obrigatório |
| SECRET_KEY | Secret exclusivo, aleatório, pelo menos 50 caracteres; nunca versionar |
| DATABASE_URL | URL interna do futuro PostgreSQL Render, mesma região do web |
| ALLOWED_HOSTS | Host público exato, sem esquema/wildcard; separar hosts por vírgula |
| CSRF_TRUSTED_ORIGINS | Origem HTTPS exata correspondente aos hosts autorizados, sem barra final ou caminho |
| PORT | Fornecida pelo Render; não precisa de valor manual |
| CORS_ALLOWED_ORIGINS | Opcional; vazio se não houver frontend de outra origem |
| MUSICBRAINZ_USER_AGENT | Opcional; identificação pública apropriada da aplicação |

Não há fallback para SQLite em `config.render`. Sem DATABASE_URL o runtime
falha de forma fechada; build de estáticos continua independente. Não preencher
com banco fictício para tentar publicar a aplicação antes da Fase 2.

HTTPS é obrigatório, cookies de sessão/CSRF permanecem seguros, CSRF middleware
permanece ativo. Render usa X-Forwarded-Proto; a configuração confia nesse proxy
quando executada atrás do Render. Não publicar diretamente esse container com
headers de proxy arbitrários. AWS conserva sua configuração CloudFront existente.
`/health/` pode usar HTTP para sondagem interna e não consulta banco; `/readiness/`
permanece HTTPS, executa SELECT 1 e responde 503 sem expor detalhes se o banco falhar.
Conferir também o Host utilizado pelas sondagens durante o primeiro deploy; não
contornar falhas ampliando ALLOWED_HOSTS para wildcard.

## PostgreSQL futuro e TLS

A conexão interna Render usa certificados autoassinados, sem suporte a verify-full.
Somente `config.render` define sslmode=require se a URL não especificar modo:
criptografa o tráfego, mas não autentica CA/hostname como verify-full. Essa diferença
é explícita, não deve ser aplicada ao RDS. Modos disable/allow/prefer são rejeitados.
verify-full continua permitido quando houver endpoint e CA compatíveis, exigindo
sslrootcert. connect_timeout é limitado a 1–30s, padrão 5s.

Na Fase 2, usar conexão interna de banco na mesma região, restringir/desativar acesso
externo quando não necessário e validar TLS real e readiness. Não consultar nem
publicar secrets nos logs. Quando usar acesso externo autorizado para exportação,
restringir IPs, usar TLS e remover a liberação depois. Nenhuma conexão Render foi
feita nos testes de configuração desta fase.

## Blueprint e migrações no Free

`render.yaml` descreve somente **um web service Free**; não contém seção databases,
discos, jobs ou planos pagos. DATABASE_URL e secrets exigem configuração manual
(`sync: false`). Auto-deploy está desligado. O arquivo sozinho não cria recursos,
mas aplicar um Blueprint cria o serviço e pode iniciar o primeiro deploy: **não
aplicar nem conectar serviços antes da autorização da Fase 2**. A região omitida
usa o padrão do Render; escolher/revisar a mesma região para web e banco antes de
criar ambos. Não há promessa de reservar nome ou domínio nesta preparação.

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

## Fase 2 — somente após autorização

1. Revisar/testar e autorizar publicação dos arquivos, sem acionar workflows AWS.
2. Definir se os dados serão novos dados acadêmicos ou migração de um banco existente;
   backup e restauração precisam ser ensaiados antes de transferir dados reais.
3. Criar PostgreSQL **Free** próximo da data em que começarão os testes de hospedagem.
   Prazo de 30 dias começa na criação: verificar expiração exata no painel e garantir
   cobertura de 06/11/2026 com margem. Evitar adiar ao ponto de não haver tempo de teste.
4. Criar o web **Free** na mesma região, sem auto-deploy; preencher variáveis acima
   no canal seguro da plataforma, com o host efetivamente atribuído.
5. Revisar o comando de startup e autorizar primeiro deploy. A criação do serviço
   pode iniciar esse deploy; por isso criação e primeiro deploy precisam de aprovação.
6. Conferir migrações concluídas, /health/ e /readiness/ 200, TLS, login/permissões,
   DRF, CSRF, estáticos e persistência após reinício. Provisionar usuário inicial
   por procedimento operacional separado, nunca senha em fixture/script público.
7. Fazer exportações lógicas independentes e testar restauração antes da entrega.
   Free não possui backups gerenciados; 1 GB de limite e expiração em 30 dias.
   Não depender do prazo de graça: banco expirado fica inacessível sem upgrade.
8. Abrir/testar a aplicação antes da apresentação para acomodar cold start. Após
   15 minutos sem tráfego Free suspende; retorno pode levar cerca de um minuto.
   Existem limites de 750 horas/workspace, tráfego e build; monitorar uso sem
   configurar upgrades automáticos ou planos pagos.

Recursos AWS permanecem intactos e podem continuar gerando custos. Desativação
posterior exige autorização própria; não é parte desta fase.

## Validação local da Fase 1

- 199 testes Django passaram com config.test_settings e SQLite temporário,
  incluindo os testes existentes AWS, DRF, WhiteNoise, importação e permissões.
- Cinco novos testes Render verificam TLS, configurações inseguras rejeitadas,
  proxy/cookies/CSRF, probes e manutenção do desenvolvimento SQLite.
- Checks Django normal e deploy passaram com configuração Render e credenciais
  exclusivamente fictícias, sem abrir conexão PostgreSQL.
- Revisão adicional rejeita listas CSRF vazias após separar vírgulas, origens
  com barra final/caminho e portas inválidas; os casos têm cobertura nos testes.
- Aplicação WSGI carregada com configuração Render. O comando real do Blueprint
  foi exercitado via Git Bash com executáveis fictícios: PORT explícita e fallback
  10000 funcionam; migração com código 17 encerra o comando com 17, sem iniciar
  Gunicorn. Esse ensaio não executa migrações nem substitui o teste do container.
- Gunicorn real não pode iniciar neste Windows: depende do módulo Unix `fcntl`.
  Validar sua inicialização em Linux/Docker, sem instalar ferramentas nesta fase.
- Blueprint validado por parser YAML e conferência local de plano Free, ausência
  de databases e auto-deploy off. Não foi aplicado/validado via API Render.
- Build Docker não executado: docker não está disponível neste ambiente.
  Deve ser validado antes de autorizar o primeiro deploy, incluindo porta PORT,
  usuário sem privilégios, estáticos e startup com PostgreSQL de teste.
- Integração PostgreSQL Render/TLS real, memória disponível e health check do proxy
  permanecem validações da Fase 2; sucesso local não comprova operação hospedada.

## Referências

- https://render.com/docs/free
- https://render.com/docs/deploys
- https://render.com/docs/docker
- https://render.com/docs/postgresql-creating-connecting
- https://render.com/docs/blueprint-spec
