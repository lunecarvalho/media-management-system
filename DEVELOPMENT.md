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

A imagem padrão usa Gunicorn como usuário sem privilégios. O Compose de produção é separado e exige configuração explícita: consulte [AWS](docs/aws.md). Docker não foi executado localmente nesta retomada.

## Variáveis

| Nome | Uso |
| --- | --- |
| DJANGO_SETTINGS_MODULE | config.settings local; config.production na imagem |
| DEBUG, SECRET_KEY, ALLOWED_HOSTS | Configuração básica; produção exige ambiente explícito |
| DATABASE_URL | Conexão PostgreSQL; produção exige verify-full e CA |
| DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT, DB_ENGINE | Alternativa somente local |
| TEST_DATABASE_URL | Banco isolado para executar testes PostgreSQL |
| CSRF_TRUSTED_ORIGINS | Origens confiáveis, somente HTTPS em produção |
| CORS_ALLOWED_ORIGINS | Vazio por padrão; habilitar somente se necessário |
| TRUST_PROXY_HEADERS | Somente atrás de proxy controlado |
| SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS | HTTPS; produção força redirecionamento |
| MUSICBRAINZ_USER_AGENT | Identificação real e contato para o serviço |
| MOVIES_DATASET_PATH | Caminho opcional do catálogo auxiliar |
| LOCAL_UID, LOCAL_GID | Usuário do Compose de desenvolvimento |
| RDS_CA_PATH | Certificado público montado no Compose de produção |

## Organização e manutenção

acervo contém modelos, serviços transacionais, importação e leitor. movimentacoes mantém auditoria. usuarios centraliza autorização; api utiliza as mesmas regras. integracoes contém clientes e catálogo auxiliar. config separa configurações local, teste, build estático e produção.

Não altere estoque diretamente via update/queryset sem o serviço: isso contornaria a auditoria. Documentação de [permissões](docs/architecture.md) e [integrações](docs/data-import.md) descreve os fluxos suportados.

Os workflows estão separados: ci.yml valida, project-automation.yml reconcilia Issues do Project #3, deploy.yml prepara implantação manual com bloqueios. Não habilite CD nem automação remota sem revisar suas configurações e permissões.

## Roadmap restante

1. Reexecutar o CI após alterações: a matriz e o build anteriores já foram validados remotamente pelo mantenedor.
2. Ensaiar migração de uma cópia dos dados reais e restauração de backup.
3. Preservar a automação do Project #3, já validada remotamente pelo mantenedor.
4. Revisar custos e segurança AWS; criar homologação somente após autorização.
5. Validar HTTPS, logs, health check e fluxos reais antes de autorizar produção.
6. Futuramente: armazenamento de capas, outras fontes de metadados e avaliação formal de acessibilidade.

Não há alegação de conformidade WCAG ou de atualização automática do dashboard em tempo real.

Preparação de homologação: [OIDC, permissões, custos e rollback](docs/aws-operations.md).
Nenhum recurso AWS é criado por comandos de validação local. O deploy permanece
manual, condicionado ao CI, à variável de ativação e à aprovação do Environment.
