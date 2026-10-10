# Deploy de 06/10/2026: diagnóstico e preparação local

## Diagnóstico

A causa raiz de `UpdateStack: ValidationException: S3 error: Access Denied`
permanece inconclusiva. O ZIP foi lido com sucesso. O evento CloudFormation não
contém parâmetros que identifiquem o template enviado. As referências externas
do template aceito não demonstram qual objeto foi negado na tentativa rejeitada.
Não há justificativa comprovada para ampliar IAM ou alterar buckets.

A sessão OIDC foi criada às 12:01:19 UTC, com duração de uma hora, sem `policy`
ou `policyArns` registrados. `PackedPolicySize: 26` não prova restrição de sessão.
A política inline registrada às 01:30:49 UTC é idêntica à atual.

## Mudanças locais

- Separação de upload/registro, solicitação e espera/validação no workflow.
- Coleta de diagnóstico mesmo se uma etapa falhar após autenticação AWS.
- Artefato com estados anterior/final, versão esperada e correlações dos eventos
  da última hora, retido por sete dias. A janela pode incluir outra operação;
  os eventos não são atribuídos automaticamente à tentativa atual.
- Somente campos permitidos são preservados. Mensagens, respostas brutas,
  stderr do CLI e configurações de aplicação não entram no relatório.
- Falha de coleta não altera o resultado da implantação. Cancelamento forçado
  ou encerramento do runner pode impedir a coleta, mesmo com `always()`.
- A checagem existente de versão ativa, Ready e Green continua obrigatória.
  Ready/Green com versão nula não passa na validação final. Uma versão anterior
  nula continua permitida antes do deploy, mas não oferece rollback de aplicação.

Estas mudanças melhoram diagnóstico; não corrigem comprovadamente o erro S3.
O script não consulta CloudTrail nem exige novas permissões IAM. Consultas EB
Describe já estão cobertas pela política examinada. No runner, usa a sessão OIDC;
para uso local, informar `--profile mediatrack-production --region sa-east-1`.
Não executar localmente sem esses argumentos. Nenhuma credencial é configurada.

## Plano de aplicação, sujeito a aprovação

Validação local atualizada: os sete testes de `config.tests.test_deploy` e os
186 testes da suíte completa passaram com `--settings=config.test_settings
--noinput`, sem banco operacional. A suíte completa precisou ser repetida fora
do sandbox devido a PermissionError nos diretórios temporários. `git diff
--check` passou. PyYAML 6.0.3 do Python do sistema validou a sintaxe do workflow
e sua estrutura básica (13 etapas, IDs únicos, workflow_dispatch presente).
Isso não substitui a validação semântica das expressões pelo GitHub Actions.
Nenhum workflow GitHub, build Docker ou deploy foi executado nesta etapa.

1. Revisar o diff e os resultados dos testes locais. Não houve push ou deploy.
2. Encaminhar os identificadores abaixo à AWS para obter bucket/key, identidade
   e razão da negação no acesso feito pelo CloudFormation.
3. Somente após evidência específica, preparar um diff exato da eventual mudança
   de infraestrutura, seu escopo mínimo e reversão. Não há mudança IAM proposta.
4. Obter aprovação explícita antes de push, merge, mudança AWS ou deploy.
5. Para eventual deploy: confirmar estado atual, backup/migrações, versão anterior
   utilizável e janela operacional. Com versão nula, definir recuperação antes.
6. Acompanhar versão/saúde e realizar smoke test/readiness após aprovação.

Riscos: a nova coleta acrescenta consultas Describe e upload de um pequeno
artefato ao GitHub; pode faltar evidência se o runner for interrompido. Um futuro
deploy conserva os riscos de indisponibilidade e incompatibilidade com o banco.
Reverter o workflow exige restaurar apenas as alterações descritas no diff;
isso não reverte uma aplicação já implantada. Rollback AWS depende de versão
anterior válida e compatibilidade de schema, com autorização separada.

## Correlação para AWS Support

- Conta/região: `167529901671` / `sa-east-1`.
- Ambiente: `MediaTrack` / `mediatrack-production` / `e-tt46mpr2kw`.
- Stack: `awseb-e-tt46mpr2kw-stack`.
- Falha: `2026-10-06T12:01:34Z`; GitHub run: `37460072449`.
- Sessão: `MediaTrackGitHubDeployRole/mediatrack-37460072449`.
- STS EventId: `9f2dc952-2f66-462a-9459-55463dca1f4e`.
- STS RequestId: `e6fc7f96-26f3-408f-8298-c5e0a4e7b0a2`.
- CloudFormation EventId: `e009810a-38bb-4c48-8535-0f4b2002321c`.
- CloudFormation RequestId: `1520c8e3-a9b7-45d9-a7c9-59d249b426ae`.
- EB RequestId: `0551065c-a3e3-47c1-8461-3c7345e7139c`.

## Plano operacional de recuperação (não executado)

### Alternativas

1. Recuperar o ambiente atual, preservando rede, roles, DNS, banco e plataforma.
   Menor mudança; risco de indisponibilidade durante o deploy AllAtOnce. Uma
   reaplicação isolada não é correção comprovada do Access Denied. Se aprovada,
   limitar a uma tentativa, com a versão já registrada e o mesmo executor OIDC,
   sem novo upload ou criação de versão; interromper se o erro repetir.
   Sem custo fixo adicional previsto, mas há consumo normal de compute/logs/S3.
   Com VersionLabel nula, não existe rollback de aplicação previamente validado.
   Correção definitiva de autorização exige identificar o objeto negado; nenhuma
   alteração IAM/bucket deve ser aplicada antes disso.
2. Associar uma operations role dedicada ao ambiente atual. Muda a identidade
   usada pelo EB em serviços downstream; não prova resolver acesso ao template.
   Afeta IAM e configuração operacional EB, exige revisão de trust/policies,
   AssociateEnvironmentOperationsRole e iam:PassRole no ARN exato. A política da
   role depende das operações efetivas, não deve ser inventada. Reversão por
   DisassociateEnvironmentOperationsRole (se antes não havia role) ou associação
   da role anterior. Sem compute duplicado; aumenta superfície de autorização.
   Recurso documentado pela AWS como beta; não recomendado como primeira ação.
3. Criar ambiente paralelo, mantendo o atual e sem trocar tráfego até aprovação.
   Afeta stack nova, EC2/ASG, EBS, SG, IP público e, conforme desenho, ALB/logs;
   não criar nem acoplar RDS ao EB. Pode exigir regra adicional de acesso ao RDS.
   Duplica custos desses recursos enquanto coexistirem; EB não cobra taxa própria.
   Não garante contornar o erro S3 com o mesmo executor. Não clonar sem revisar
   configurações; segredos devem permanecer em canal seguro. Impedir jobs e
   escritas de validação no banco produtivo. CNAME swap só após testes e aprovação;
   DNS customizado apontado diretamente ao ALB/IP requer plano separado.
   Reverter tráfego por swap inverso/DNS anterior, respeitando caches; preservar
   ambiente antigo. Se o antigo não executa MediaTrack, esse retorno não recupera
   a aplicação. Terminação posterior é destrutiva e exige outra aprovação.

### Recomendação e etapas executáveis

Priorizar ambiente atual. Não recomendar rebuild, troca de plataforma, abertura
de buckets ou concessão global de S3. Aprovar separadamente uma única tentativa
controlada de recuperação e qualquer correção definitiva que a AWS identificar.

Antes da tentativa:

1. Reconfirmar conta/perfil readonly, Ready, ausência de operação concorrente,
   stack estável e versão registrada com SourceBundle existente.
2. Validar pacote/imagem correspondente em CI; confirmar que schema existente é
   compatível. Não rodar migrate nem smoke tests que gravem dados produtivos.
3. Confirmar configuração segura de produção, CA do RDS, conectividade e domínio
   HTTPS por checks que não imprimam valores. Sem esses pré-requisitos, não iniciar.
4. Registrar estado anterior e declarar indisponibilidade de rollback se versão
   nula. Obter aprovação para janela e risco de indisponibilidade.
5. Preparar uma execução manual que reutilize exatamente a versão
   `mediatrack-53075e0d70d8ef688b0a2cf6fe808f3454e728a3-37460072449-1`.
   O workflow atual gera versão nova; não usar seu workflow_dispatch para esta
   tentativa sem adaptação local previamente revisada. Executar somente via role
   GitHub já existente, nunca promovendo o perfil readonly a escritor.

Depois de aprovação: uma chamada UpdateEnvironment com EnvironmentName e
VersionLabel exatos acima, seguida de waiter e validação. Limite operacional de
30 minutos; timeout implica parar novas ações e verificar estado, não cancelar
ou reverter automaticamente. Se Access Denied repetir, encerrar tentativas e
encaminhar as correlações ao AWS Support. Não criar ambiente automaticamente.

### Permissões da alternativa mínima

Nenhuma permissão adicional proposta para a role GitHub para solicitar a tentativa:
- elasticbeanstalk:UpdateEnvironment no ARN
  `arn:aws:elasticbeanstalk:sa-east-1:167529901671:environment/MediaTrack/mediatrack-production`;
- elasticbeanstalk:DescribeEnvironments e DescribeEvents (consulta/wait/diagnóstico);
- cloudformation:UpdateStack na stack atual e suas permissões de leitura;
- s3:GetObject no ZIP e nos objetos regionais já autorizados.

Essas permissões já constam da política examinada. Isso não garante suficiência
para a leitura S3 desconhecida que falhou; a permissão corretiva exata ainda não
pode ser determinada. Não propor s3:GetObject em buckets externos só por hipótese.
Não são necessários novos PutObject, CreateApplicationVersion, iam:PassRole,
CreateEnvironment, EC2 write ou RDS write na interface da tentativa mínima.
Se houver outra falha downstream, parar e revisar o evento antes de autorizar mais.
O perfil `mediatrack-production` permanece somente leitura; não executar mutações
com ele. A execução OIDC deve ser aprovada separadamente.

### Critérios de aceite

- VersionLabel exatamente igual à versão aprovada, Status Ready e Health Green
  em cinco observações consecutivas com um minuto entre elas; nenhum ERROR EB
  novo associado à atualização. Registrar estado final da stack.
- HTTPS válido no domínio final, sem loops; `/health/` e `/readiness/` retornam
  HTTP 200 e JSON status ok em cinco observações. Readiness testa SELECT 1.
- Login com conta de teste existente e leitura do acervo/API autorizada funcionam;
  usuário sem permissão continua bloqueado. Sem criação/alteração de registros.
- CSS/JS essenciais retornam 200 e conteúdo correto; nenhum 5xx nas verificações.
- Resultado da etapa de validação e relatório preservado, sem dados sensíveis.

### Fontes operacionais

- https://docs.aws.amazon.com/elasticbeanstalk/latest/api/API_AssociateEnvironmentOperationsRole.html
- https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features.CNAMESwap.html
- https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/Welcome.html

## Mecanismo manual preparado (não executado)

O arquivo `.github/workflows/recover.yml` implementa a tentativa acima. Possui
somente confirmação booleana; conta, role, região, ambiente, EnvironmentId,
versão, bucket/key, tamanho e ETag são fixos e reconferidos pelo script
`scripts/recover_eb.py`. Não usa variáveis GitHub para escolher esses destinos.
Compartilha o lock `aws-production` com o deploy normal; cancel-in-progress é
false. Só roda na main do repositório aprovado, após CI, no environment
aws-production, com AWS_DEPLOY_ENABLED=true. As proteções/revisores existentes
desse environment continuam aplicáveis; nenhuma configuração GitHub foi alterada.

Preflight realizado com perfil readonly: passou. ZIP disponível, 98.945 bytes,
AES256, ETag fixado. Configurações necessárias presentes, incluindo referências
de SECRET_KEY e DATABASE_URL a secrets. Não foram consultados valores dos secrets:
presença não prova resolução, permissões da instância, TLS ou conectividade RDS.
Settings module, DEBUG, hosts e origem HTTPS são verificados sem imprimir valores.
O teste HTTP usa origem HTTPS correspondente a host permitido, derivada da
configuração atual do ambiente, sem aceitar origem por input e sem seguir redirects.

Procedimento futuro, somente após aprovação e publicação autorizada do workflow:
GitHub > Actions > MediaTrack controlled recovery (existing version only) >
Run workflow > branch main > confirm=true. Não executar o deploy.yml normal.
O mecanismo invoca `python scripts/recover_eb.py --execute` no runner OIDC.
Única chamada de mutação, com região explícita:

```sh
aws elasticbeanstalk update-environment \
  --environment-name mediatrack-production \
  --version-label mediatrack-53075e0d70d8ef688b0a2cf6fe808f3454e728a3-37460072449-1 \
  --region sa-east-1
```

Essa chamada não deve ser executada com o perfil readonly. O wrapper captura e
descarta respostas brutas e desativa retries do AWS CLI. Não há upload, criação
de versão, migração, troca de plataforma, DNS, IAM ou cancelamento de operação.
Uma atualização de aplicação pode alterar recursos da stack e reiniciar/substituir
instâncias conforme o comportamento do EB; não há promessa de EC2 imutável.

Erros ERROR/FATAL do ambiente desde o início interrompem a verificação. Nenhuma
nova chamada UpdateEnvironment é feita pelo script. Prazo de 30 minutos, mais
latência limitada das consultas, e timeout do job de 40 minutos. Exige cinco
observações consecutivas de versão exata, Ready/Green, ausência de operação
abortável e HTTP 200 com JSON status ok em health/readiness, separadas por 60s.
Falhas transitórias reiniciam a contagem. Diagnóstico sanitizado roda em always;
sucesso preserva também eb-recovery.json. Interrupção do runner pode impedir coleta.
Login/acervo/estáticos permanecem aceite operacional manual somente leitura.

Sem versão anterior ativa, rollback da aplicação não está disponível. Nova
tentativa, cancelamento ou ambiente paralelo exigem aprovação separada. O mesmo
Access Denied pode reaparecer: este mecanismo não corrige sua causa desconhecida.
Publicação na main autorizada exclusivamente para preparar a recuperação.
Validação antes da publicação: 194 testes passaram, ambos os YAMLs foram
validados com PyYAML e os sete arquivos foram revisados sem identificação de
segredos ou credenciais reais. O push pode iniciar o CI normal; os workflows
de deploy e recuperação são exclusivamente manuais. A execução da recuperação
e qualquer alteração AWS continuam sem autorização.
