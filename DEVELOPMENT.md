# Desenvolvimento do MediaTrack

## Instalação local

Utilize Python 3.14, conforme .python-version. As dependências diretas estão fixadas em requirements.txt.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No Linux, ative com `source venv/bin/activate` e copie com `cp .env.example .env`.
Edite .env somente localmente. Para SQLite, deixe DATABASE_URL e DB_HOST ausentes/vazios e utilize DEBUG=True em desenvolvimento. Variáveis do processo prevalecem sobre .env: um DEBUG inválido exportado pelo terminal causa erro explícito. Nunca use a chave de exemplo em produção.

Em banco novo:

```text
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse localhost:8000 e /admin/. Em banco existente, faça backup e siga a estratégia de migração em [arquitetura](docs/architecture.md) antes de migrate. Não execute comandos de desenvolvimento contra produção.

## Testes

```text
python -m pip check
python manage.py check --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings
python manage.py test --noinput --settings=config.test_settings
python manage.py collectstatic --noinput --settings=config.static_settings
python scripts/build_bundle.py
```

config.test_settings isola SQLite em memória, desativa o redirecionamento HTTPS apenas nos testes e usa hash rápido apenas para testes. A aplicação de produção não usa essas configurações.

Para PostgreSQL, configure TEST_DATABASE_URL apontando para um banco exclusivamente de testes, com usuário autorizado a criar/remover bancos de teste, e execute a mesma suíte. Não use a URL de produção. O CI executa a matriz SQLite/PostgreSQL 16. O teste de preservação de dados legados usa um subprocesso SQLite independente; isso não substitui ensaiar a migração do banco real em uma cópia PostgreSQL.

Para desenvolvimento com PostgreSQL, DATABASE_URL tem prioridade sobre DB_HOST/DB_NAME/DB_USER/DB_PASSWORD/DB_PORT. Credenciais com caracteres especiais devem ser codificadas na URL. O parser é dj-database-url e o driver é psycopg 3.

## Docker

```text
docker build -t mediatrack .
docker compose up --build
```

O Compose padrão é exclusivamente de desenvolvimento: PostgreSQL 16, volume local e runserver. Executa migrações ao iniciar, portanto use somente banco de desenvolvimento. No Linux, ajuste LOCAL_UID e LOCAL_GID para permitir escrita no diretório montado. Não remova o volume para resolver falhas sem preservar seus dados.

A imagem padrão usa Gunicorn como usuário sem privilégios e aceita `PORT`, com
fallback 8000. O Render substitui o comando de início para executar migrações antes
do Gunicorn; elas não rodam no build e uma falha impede o servidor de iniciar.
Consulte o [guia principal de implantação no Render](docs/render.md).
O Compose de produção existente é da configuração AWS legada, exige configuração
explícita e não é um procedimento Render: consulte o [histórico AWS](docs/archive/aws.md).
O build Docker e o Gunicorn real em Linux permanecem pendentes de validação.

### Configurações de ambiente

- `config.settings`: desenvolvimento, com SQLite quando `DATABASE_URL` e `DB_HOST`
  estão vazios; use `DEBUG=True` somente localmente.
- `config.render`: hospedagem escolhida; exige `DEBUG=False`, PostgreSQL, secrets
  no ambiente, hosts exatos e origens HTTPS. Usa `X-Forwarded-Proto` do proxy Render.
  TLS padrão `sslmode=require` criptografa sem autenticar CA/hostname; rejeita
  modos que permitem conexão sem TLS. `verify-full` exige CA e endpoint compatíveis.
- `config.production`: configuração AWS legada, ainda padrão da imagem; exige
  PostgreSQL com `sslmode=verify-full` e `sslrootcert`. Sua política não foi
  enfraquecida pela preparação Render. O Render deve definir explicitamente
  `DJANGO_SETTINGS_MODULE=config.render`.

## Variáveis

| Nome | Uso |
| --- | --- |
| DJANGO_SETTINGS_MODULE | config.settings local; config.render no Render; config.production padrão da imagem/AWS legado |
| DEBUG, SECRET_KEY, ALLOWED_HOSTS | Configuração básica; produção exige ambiente explícito |
| DATABASE_URL | PostgreSQL: Render exige TLS require por padrão; AWS legado exige verify-full e CA |
| DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT, DB_ENGINE | Alternativa somente local |
| TEST_DATABASE_URL | Banco isolado para executar testes PostgreSQL |
| CSRF_TRUSTED_ORIGINS | Origens confiáveis, somente HTTPS em produção |
| CORS_ALLOWED_ORIGINS | Vazio por padrão; habilitar somente se necessário |
| TRUST_PROXY_HEADERS | AWS legado: somente atrás de proxy controlado; Render configura seu próprio cabeçalho |
| SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS | HTTPS; produção força redirecionamento |
| MUSICBRAINZ_USER_AGENT | Identificação real e contato para o serviço |
| DVD_DATASET_PATH | Caminho do SQL de DVDs; padrão datasets/bd_model-criacao.sql |
| LOCAL_UID, LOCAL_GID | Usuário do Compose de desenvolvimento |
| RDS_CA_PATH | AWS legado: certificado público montado no Compose de produção |
| PORT | Porta fornecida pelo Render; imagem usa fallback 8000 e comando Render usa 10000 |

## Metadados de CDs e DVDs

CDs utilizam MusicBrainz, com verificação explícita de formato. DVDs utilizam a base
EAN/UPC do grupo importada no mesmo banco Django. Sem resultado, o cadastro manual
preserva o código. Consulte [importação e limitações](docs/data-import.md).

Depois de aplicar as migrações e disponibilizar `datasets/bd_model-criacao.sql`:

```text
python manage.py importar_filmes
```

O arquivo `datasets/bd_model-criacao.sql` está versionado e contém a base auxiliar
local de referências de DVDs; os demais arquivos de `datasets/` permanecem ignorados
pelo Git. O dataset não faz parte da imagem Docker de produção nem do ZIP padrão
de deploy do Elastic Beanstalk (legado). Quando desejada, a importação é um procedimento
operacional separado: disponibilize o arquivo ao comando Django, que persiste os
dados via ORM. O runtime normal não executa esse SQL diretamente. A aplicação
funciona sem a importação, mas a identificação local dos DVDs dessa base fica
indisponível. Repetir o comando ignora dados idênticos e atualiza referências
alteradas, sem modificar produtos/exemplares já cadastrados.

Testes dessa integração (MusicBrainz simulado):

```text
python manage.py test integracoes acervo.tests.test_dvd_flow acervo.tests.test_barcode_flow --settings=config.test_settings
node --test acervo/tests/js/barcode.test.cjs acervo/tests/js/cadastro-item.test.cjs
```

## Organização e manutenção

acervo contém modelos, serviços transacionais, importação e leitor. movimentacoes mantém auditoria. usuarios centraliza autorização; api utiliza as mesmas regras. integracoes contém clientes e catálogo auxiliar. config separa configurações local, teste, build estático e produção.

Não altere estoque diretamente via update/queryset sem o serviço: isso contornaria a auditoria. Documentação de [permissões](docs/architecture.md) e [integrações](docs/data-import.md) descreve os fluxos suportados.

Os workflows estão separados: ci.yml valida e project-automation.yml reconcilia
Issues do Project #3. deploy.yml e recover.yml pertencem ao histórico AWS, não ao
procedimento Render. Não habilite CD nem automação remota sem revisar suas
configurações e permissões. A implantação escolhida está em [Render](docs/render.md).

## Roadmap restante

1. Reexecutar o CI após alterações: a matriz e o build anteriores já foram validados remotamente pelo mantenedor.
2. Ensaiar migração de uma cópia dos dados reais e restauração de backup.
3. Preservar a automação do Project #3, já validada remotamente pelo mantenedor.
4. Validar o container em Linux/Docker e planejar PostgreSQL Free, região, secrets,
   importação e backups; criar serviços Render somente após autorização.
5. Validar HTTPS, logs, health check e fluxos reais antes de autorizar produção.
6. Futuramente: armazenamento de capas, outras fontes de metadados e avaliação formal de acessibilidade.

Não há alegação de conformidade WCAG ou de atualização automática do dashboard em tempo real.

Próxima etapa: [Fase 2 no Render](docs/render.md). Nenhum serviço ou banco Render
foi criado e nenhum deploy Render foi realizado. O primeiro deploy exige aprovação.
O [roteiro AWS arquivado](docs/archive/aws-operations.md) é referência histórica;
suas variáveis de ativação e Environment não controlam a implantação Render.
