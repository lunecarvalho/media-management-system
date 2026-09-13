# Docker e AWS — preparação sem implantação

Arquitetura: GitHub Actions → Elastic Beanstalk com plataforma Docker de um container → Gunicorn/Django → RDS PostgreSQL 16. Python 3.14 vem da imagem; não depende da oferta de Python nativo do Beanstalk. WhiteNoise entrega estáticos. S3 para capas/mídia fica como evolução; o bucket de artefatos do futuro CD tem outra finalidade.

Nenhum recurso foi criado. Antes de criar infraestrutura, confira preços, créditos/Free Tier, disponibilidade regional, orçamento e alertas. Não há garantia de gratuidade. Render permanece apenas alternativa usando os mesmos requisitos de produção.

## Imagem e pacote

Dockerfile instala dependências fixadas, coleta estáticos no build, executa como usuário sem privilégios e inicia Gunicorn em config.wsgi:application na porta 8000. Não executa migrate ou runserver. A base python:3.14-slim acompanha atualizações de segurança: não é uma imagem fixada por digest e pode mudar entre builds. O ZIP tem conteúdo ordenado e timestamps fixos; isso não promete imagens bit a bit idênticas.

```text
docker build -t mediatrack .
python scripts/build_bundle.py
python scripts/build_bundle.py --rds-ca CAMINHO_DO_BUNDLE_PUBLICO
```

O ZIP em dist/mediatrack.zip usa allowlist, inclui Dockerfile na raiz e exclui Compose, .env, banco local, datasets, Git, credenciais e testes. .dockerignore protege também o contexto de build direto. O parâmetro rds-ca valida um certificado público e o inclui em certs/rds-ca.pem; rejeita chave privada. Obtenha a CA pela fonte oficial RDS, revise origem e renovação. Não versione certificados locais.

Para ensaio com PostgreSQL configurado, defina as variáveis requeridas em docker-compose.prod.yml, monte a CA pública usando RDS_CA_PATH e execute:

```text
docker compose -f docker-compose.prod.yml up --build
```

Esse Compose exige sslrootcert=/run/certs/rds.pem na URL. Na imagem criada a partir do ZIP com CA incluída, use /app/certs/rds-ca.pem. Não misture os caminhos. O redirecionamento HTTPS permanece ativo: ensaie atrás de proxy HTTPS controlado. /health/ aceita HTTP para sondagem interna.

Docker não executado localmente. O CI está preparado para construir a imagem do ZIP e testar importações de dependências; valide também o funcionamento completo da imagem em homologação.

## Configuração manual do Beanstalk e RDS

Após autorização e revisão de custos:

1. Escolher plataforma Docker suportada no Beanstalk, com proxy e balanceador HTTPS. Não usar docker-compose.yml de desenvolvimento como pacote EB.
2. Provisionar RDS separadamente, com backup, retenção e proteção de exclusão; não vincular seu ciclo de vida ao ambiente descartável. Permitir 5432 somente a partir do security group da aplicação.
3. Configurar certificado HTTPS no balanceador e hosts exatos. TRUST_PROXY_HEADERS somente para proxy controlado que sobrescreve X-Forwarded-Proto. Verificar redirecionamentos e cookies pelo domínio definitivo.
4. Fornecer DJANGO_SETTINGS_MODULE, DEBUG, SECRET_KEY, DATABASE_URL e ALLOWED_HOSTS no ambiente. config.production exige configuração explícita, PostgreSQL e DEBUG desativado. SECRET_KEY deve ser aleatória, exclusiva e ter pelo menos 50 caracteres.
5. DATABASE_URL deve usar o endpoint real do RDS e sslmode=verify-full, sslrootcert para a CA disponível no container; pode adicionar connect_timeout. Essa combinação verifica cadeia e hostname. Nunca trocar por require/disable para contornar erro de certificado.
6. Configurar CSRF_TRUSTED_ORIGINS com origens HTTPS necessárias. CORS_ALLOWED_ORIGINS deve permanecer vazio se não houver cliente de outra origem. Cookies seguros e redirecionamento HTTPS são obrigatórios.
7. Configurar /health/ como health check. A rota pública verifica disponibilidade do banco e retorna somente status genérico, HTTP 200 ou 503, sem detalhes. Configure a sondagem/proxy com Host aceito pelo Django: ALLOWED_HOSTS continua sendo verificado. Não resolver health check com wildcard de hosts.
8. Revisar logs e retenção, sem headers de autorização, corpos ou credenciais. A imagem usa stdout/stderr. Confirmar estratégia de monitoração no ambiente real.

Não são necessários Procfile nem WSGIPath da plataforma Python: o Dockerfile define o processo e a porta da plataforma Docker. collectstatic utiliza config.static_settings somente no build, sem banco/segredo de produção. Nunca use esse settings para servir requisições. WhiteNoise usa arquivos comprimidos e nomes com hash; mídia enviada por usuários exigirá estratégia própria no futuro.

## Migrações e primeira criação do banco

Crie usuário/banco operacional com privilégios adequados e acesso de rede restrito. Use um banco separado para testes. Credenciais devem vir do ambiente ou de mecanismo seguro de secrets suportado pela plataforma, nunca do pacote.

Antes de alterar um banco existente: backup consistente e restauração testada, auditoria de dados legados, migração ensaiada em cópia PostgreSQL e janela de manutenção. Com a imagem da versão aprovada e as variáveis de produção, execute uma única vez:

```text
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --plan
python manage.py migrate --noinput
```

Não execute automaticamente em cada worker. A migração Produto/Exemplar não possui rollback automático; restauração e rollback da aplicação precisam ser planejados juntos. Interrompa se os dados violarem constraints. Crie o primeiro usuário administrador pelo procedimento operacional autorizado, sem senha no script.

PostgreSQL não executado localmente; validação preparada no CI. Os testes de configuração/TLS não equivalem a conexão com RDS real.

## CI/CD preparado e bloqueado

ci.yml executa checks, ausência de migrações pendentes no código e testes em SQLite/PostgreSQL; depois collectstatic, pacote e build Docker. deploy.yml é exclusivamente workflow_dispatch, chama o mesmo CI e exige:
- AWS_DEPLOY_ENABLED habilitado explicitamente nas variáveis do repositório;
- execução na branch main;
- confirmação de deploy e confirmação de backup/migrações;
- Environment aws-production, a configurar com revisores obrigatórios.

Sem essas condições, o job de implantação não roda. Não houve execução remota nesta retomada.

Configure AWS_REGION, AWS_ROLE_ARN, EB_APPLICATION, EB_ENVIRONMENT, EB_ARTIFACT_BUCKET e RDS_CA_BUNDLE_URL. O endpoint da CA deve ser HTTPS oficial truststore.pki.rds.amazonaws.com. O workflow prepara a CA e o ZIP antes de assumir a role.

Use OIDC com audience sts.amazonaws.com e trust restrito ao repositório e Environment aws-production. Não são necessárias AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY permanentes. A role deve limitar upload ao prefixo mediatrack do bucket existente e operações EB de criar versão, atualizar/descrever o ambiente escolhido. Revise policies usando recursos reais e permissões exigidas pela configuração EB; não utilize AdministratorAccess.

O workflow não cria bucket, aplicação, ambiente, RDS ou IAM. Futuramente poderá enviar ZIP, criar versão de aplicação e atualizar ambiente existente; isso é deploy real e só deve ser autorizado após homologação. O bundle do deploy adiciona a CA ao mesmo código validado, portanto ensaie esse pacote com o certificado antes da primeira implantação.

## Checklist antes do primeiro deploy

- CI remoto verde em ambos os bancos e build Docker.
- Imagem iniciada com PostgreSQL, HTTPS, CA e health check reais.
- Backup restaurado e migração ensaiada com dados representativos.
- Conferência de IDs, vínculos, contagens e histórico após migração.
- Login, perfil inativo, CRUD, API, CSV e código de barras verificados.
- Estáticos carregados sem runserver, sem redirecionamentos em loop.
- Hosts, CSRF, cookies, logs e TLS revisados.
- Custos, alertas, OIDC e aprovação de Environment configurados.
- Plano de rollback da aplicação e do banco documentado.
- Autorização explícita antes de habilitar e executar CD.

## Referências oficiais

- [Docker no Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/single-container-docker-configuration.html)
- [OIDC GitHub/AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [TLS PostgreSQL no RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)
