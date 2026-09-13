# Homologação, OIDC e rollback — roteiro ainda não executado

Este documento não provisiona recursos. O mantenedor deve aprovar custos e operação
antes de qualquer uso do console/CLI AWS. A aplicação já possui Docker, Gunicorn,
WhiteNoise e PostgreSQL com TLS; não existe ambiente AWS validado nesta Issue.

## Separação de homologação e produção

Homologação deve ter banco, credenciais e destino próprios, usando config.production
para testar as mesmas proteções. Não usar cópia identificável de dados reais sem
necessidade. Não apontar testes automatizados ao RDS operacional.

O workflow atual utiliza o Environment GitHub `aws-production`. Não reutilizar suas
variáveis para alternar informalmente entre ambientes. Nesta etapa homologação é um
roteiro manual; um job dedicado com Environment e role próprios deve ser revisado
antes de automatizar sua implantação. Nenhum deploy foi habilitado.

## OIDC: trust policy a preencher, não aplicar agora

Usar um provider GitHub OIDC e uma role de deploy dedicados, sem access keys estáticas.
O modelo abaixo é JSON documental com placeholders, não uma policy pronta para aplicar:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "<ARN_DO_PROVIDER_OIDC_GITHUB>"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {"StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "<SUB_EXATO_DO_REPOSITORIO_E_ENVIRONMENT>"
    }}
  }]
}
```

Para o formato tradicional, o subject deste workflow é
`repo:lunecarvalho/media-management-system:environment:aws-production`.
GitHub também possui subjects com IDs imutáveis: confirme o formato utilizado pelo
repositório antes de preencher a policy; não invente IDs e não registre o JWT.
Não use wildcard no subject. O provider deve ser token.actions.githubusercontent.com.

Como o job usa Environment, o subject não é o subject de branch
`repo:lunecarvalho/media-management-system:ref:refs/heads/main`.
Não combine ambos como se o token contivesse os dois. Restrinja **Selected deployment
branches and tags** do Environment à branch main, configure revisores obrigatórios,
impeça autoaprovação e bypass quando disponíveis. O workflow também verifica main e
o repositório exato. Proteja main e alterações de workflows com revisão.

O token OIDC permite assumir a role; as permissões da role determinam as operações.
Não confundir a role GitHub com a service role EB ou o instance profile EC2.

## Permissões do deploy: base mínima a validar com os recursos reais

| Operação do workflow | Permissão / escopo proposto |
| --- | --- |
| Upload do ZIP | s3:PutObject em `<ARN_BUCKET>/mediatrack/*` |
| Upload multipart | s3:AbortMultipartUpload no mesmo prefixo, se necessário |
| EB ler pacote | s3:GetObject no prefixo; conferir permissões do serviço/instance profile que lê o pacote |
| Criar versão | elasticbeanstalk:CreateApplicationVersion na aplicação e nas versões `mediatrack-*` dessa aplicação |
| Conferir ambiente / waiter | elasticbeanstalk:DescribeEnvironments no ambiente autorizado |
| Atualizar versão | elasticbeanstalk:UpdateEnvironment no ambiente autorizado, restringindo elasticbeanstalk:FromApplicationVersion às versões da aplicação |

Use ARNs de aplicação, applicationversion e environment conforme a referência AWS,
substituindo conta, região, aplicação e ambiente reais somente depois de definidos.
O wildcard de versões é restrito à aplicação e prefixo, não a outras aplicações.
Teste a policy com simulação/revisão e CloudTrail na fase autorizada; esta base não foi
validada na conta. Não ampliar para AdministratorAccess para resolver uma negação.

Se houver SSE-KMS, serão necessárias permissões adicionais específicas na chave
(por exemplo GenerateDataKey/Decrypt conforme operação) e key policy compatível.
Não adicionar KMS sem necessidade. O fluxo não solicita CreateEnvironment,
CreateApplication, CreateBucket, operações RDS, EC2 ou IAM. Não concede iam:PassRole
ao deploy para trocar roles; o ambiente deve estar provisionado previamente.
Provisionamento e configuração de infraestrutura são procedimentos separados.

## Variáveis: onde configurar depois da aprovação

| Local | Nomes |
| --- | --- |
| GitHub Repository Variables | AWS_DEPLOY_ENABLED (manter false) |
| GitHub Environment aws-production Variables | AWS_REGION, AWS_ROLE_ARN, EB_APPLICATION, EB_ENVIRONMENT, EB_ARTIFACT_BUCKET, RDS_CA_BUNDLE_URL |
| Ambiente seguro da aplicação | DJANGO_SETTINGS_MODULE, DEBUG, SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, TRUST_PROXY_HEADERS |
| Aplicação, opcionais | CORS_ALLOWED_ORIGINS, MUSICBRAINZ_USER_AGENT, MOVIES_DATASET_PATH, SECURE_HSTS_SECONDS |

Região, ARN, nomes de recursos, endpoint RDS e domínio só podem ser preenchidos após
decisão/provisionamento autorizado. OIDC não exige Secret AWS permanente no GitHub.
SECRET_KEY e DATABASE_URL ficam no mecanismo seguro de configuração da aplicação,
nunca nos logs, YAML, pacote ou Git. Não colocar a URL do banco nas variáveis públicas
do GitHub. Credenciais não devem aparecer em comandos gravados no histórico do shell.

Produção exige PostgreSQL com sslmode=verify-full e sslrootcert, hostname e timeout
de conexão entre 1 e 30 segundos (padrão 5). Esse timeout limita a conexão, não o tempo
total de consultas. Revisar timeouts de queries/monitoramento na homologação real.

## Procedimento de deploy futuro

1. Registrar SHA e versão EB atual, backup e plano de restauração. Confirmar CI verde.
2. Ensaiar o pacote final com CA, mesma plataforma Docker, domínio HTTPS e RDS de
   homologação. Verificar login, permissões, CSV, API e estáticos com hash.
3. Validar /health/ sem dependência do banco e /readiness/ com banco disponível e
   indisponível. Readiness mantém HTTPS. Liveness 200 não comprova disponibilidade do acervo.
4. Validar Host enviado pelo health check do balanceador/proxy. O ALB pode usar IP
   privado no Host; o proxy precisa encaminhar um Host aceito pelo Django. Essa
   configuração ainda depende do ambiente real. Não utilizar ALLOWED_HOSTS=*.
5. Fazer backup verificável e janela de manutenção para migrações incompatíveis.
   Não marcar database_ready antes de executar e conferir migrações uma única vez
   em acesso operacional autorizado; GitHub runner não precisa acessar o RDS privado.
6. Após aprovação, habilitar a variável e executar workflow_dispatch na main com
   confirmações explícitas. Aprovar no Environment. Nunca executar isso nesta etapa.
7. O workflow refaz CI, constrói o ZIP com CA e sua imagem antes de OIDC; verifica
   aplicação/ambiente existente e estado Ready, registra a versão anterior, envia
   pacote e atualiza a versão. Depois exige versão esperada e Health Green.
8. Fazer smoke test pelo domínio real, incluindo readiness. Estado Ready do EB sozinho
   não prova sucesso; health ainda em transição pode reprovar a validação conservadora.
   Investigar antes de repetir, pois o deploy pode ter sido aplicado mesmo com job vermelho.

## Rollback, sem restauração automática destrutiva

- Se não houve mudança incompatível no banco, selecionar a **versão EB anterior
  registrada**, preservando seu ZIP/CA, e autorizar explicitamente o redeploy pelo
  procedimento operacional. Não reconstruir uma tag mutável esperando imagem idêntica.
- Antes de voltar código, confirmar compatibilidade com o schema atual. Não executar
  migrate reverso automaticamente; a migração Produto/Exemplar não é reversível.
- Se rollback exigir banco anterior, interromper gravações e avaliar dados criados
  desde o backup. Restaurar em **instância separada**, comparar dados, planejar corte
  de conexão e obter autorização. Restauração de RDS cria recursos e pode gerar custos.
- Não apagar banco/versões/snapshots para resolver falhas. Registrar início/fim,
  versão efetiva, resultado dos probes e perdas de dados eventualmente aprovadas.
- Testar novamente login, fluxo de estoque, auditoria, TLS e estáticos após retorno.

## Recursos: decisões pendentes, não criar agora

| Recurso / finalidade | Cobrança possível | Alternativa mais barata | Sugestão e ação manual futura |
| --- | --- | --- | --- |
| EB / EC2 / EBS: executar app | Compute, disco, tráfego e IP | Ensaio Docker local; homologação single instance | Dimensionar com medições; aprovar capacidade e criar ambiente Docker somente depois |
| Load Balancer: HTTPS e distribuição | Horas e capacidade | Single instance com proxy TLS próprio, com maior responsabilidade operacional | Preferir ALB quando orçamento permitir; configurar certificado e health Host |
| RDS: PostgreSQL | Instância, armazenamento, I/O e backups | PostgreSQL local para ensaio | Banco privado separado, backups e proteção de exclusão; avaliar single-AZ em homologação |
| S3: ZIPs | Armazenamento, requisições e tráfego | Artefatos GitHub durante preparação | Bucket privado existente/dedicado com prefixo e retenção revisada; não adicionar mídia agora |
| IAM/OIDC: autenticar deploy | Não implica compute por si; permissões habilitam ações cobradas | Manter CD desativado | Revisar trust/policy e criar role/provider apenas após aprovação |
| VPC/egresso: rede | NAT Gateway, endpoints, IPs e tráfego podem cobrar | Avaliar egress simples para homologação | Desenhar rede antes de criar; RDS não público; app precisa baixar imagem/dependências e acessar MusicBrainz |
| Route 53/domínio | Zona, consultas, registro | DNS já existente | Decidir domínio/provedor sem inventar hostname |
| CloudWatch: logs/alertas | Ingestão, retenção, métricas e alarmes | Logs locais no ensaio | Retenção curta aprovada e sem dados sensíveis; estimar volume |

Custos dependem de região, uso e configuração. Conferir calculadora/preços e créditos
antes de aprovar; não assumir gratuidade. Esta tabela é planejamento, não autorização.

## Referências

- [OIDC e subjects GitHub](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [Permissões EB por ação e recurso](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elasticbeanstalk.html)
- [Pacote e permissões de CreateApplicationVersion](https://docs.aws.amazon.com/elasticbeanstalk/latest/api/API_CreateApplicationVersion.html)
