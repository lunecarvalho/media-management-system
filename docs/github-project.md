# Kanban existente

Único destino: https://github.com/users/lunecarvalho/projects/3.
Issues de lunecarvalho/media-management-system são as tarefas.

Não foi possível consultar o Project autenticado neste ambiente. Node ID, ID do
Status, opções e itens existentes não foram inventados. O script descobre esses
valores e os imprime antes de mutações; interrompe em caso de erro.

## Preferir automações nativas

Em Project #3 > Workflows, revisar auto-add com filtro
`repo:lunecarvalho/media-management-system is:issue -label:project-ignore`, item added -> Todo e
issue closed -> Done. PR merged -> Done nativo altera o item da PR, não necessariamente
a Issue associada. Não adicionar PRs como segunda estrutura de tarefas.
https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations

## Acesso e ativação manual

GITHUB_TOKEN não acessa Projects de usuário. Configurar PROJECT_TOKEN em
Repository Settings > Secrets and variables > Actions > New repository secret.
A API de Projects documenta PAT classic com `project` para escrita (apenas
`read:project` para consulta). Neste Project pessoal, use esse escopo e acesso
público a Issues/PRs; acrescente `repo` somente se o repositório for privado.
Não presuma que permissões de Projects de organização em um fine-grained PAT
permitam acessar este Project pessoal. Usar expiração curta. GitHub App com organization
projects serve a organizações, não é substituto automático neste Project pessoal.
https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions

Executar manualmente Project 3 com apply=false; conferir IDs e Issues listados.
Após revisar automações nativas, configurar a variável PROJECT_AUTOMATION_ENABLED=true
para o complemento Actions. Pode manter somente a execução manual se as nativas
forem suficientes. Evitar automações nativas conflitantes.

## Política

Reconciliação pelo estado atual: fechada -> Done; aberta com referência de
fechamento reconhecida pelo GitHub em PR aberta -> In Progress; demais -> Todo.
Merge só implica Done quando a Issue está fechada; não encerra tarefas parcialmente
resolvidas. Reabertura e edição de vínculos são reconciliadas.
Execuções serializadas, código apenas da branch padrão e Secrets nunca impressos.
Itens existentes são reutilizados; addProjectV2ItemById opera por contentId.
A reconciliação alcança todas as Issues do repositório, inclusive antigas.

## Exclusão por project-ignore

Issues com a label `project-ignore` são ignoradas antes de calcular ou escrever
Status, abertas ou fechadas, presentes ou ausentes no Project. O script não adiciona,
atualiza, remove nem readiciona esses itens. O log informa `ignorada: project-ignore`.
A comparação do nome não diferencia maiúsculas/minúsculas e não aceita correspondência
parcial. Todas as páginas de labels são consultadas quando necessário; falhas nessa
leitura impedem escrita. O filtro issue_number continua válido: selecionar uma Issue
ignorada resulta em nenhuma ação, não em erro de Issue inexistente.

Eventos labeled/unlabeled também disparam reconciliação, respeitando os bloqueios
existentes. Remover a label permite que a Issue volte ao fluxo normal. As regras de
Todo, In Progress, In Review e Done das demais Issues permanecem iguais.

**Configuração manual pendente no GitHub:** atualizar todos os Auto-add que possam
atingir este repositório para usar `-label:project-ignore`, além da seleção exclusiva
do MediaTrack e `is:issue`. O script não controla automações nativas. Regras nativas
como Issue closed → Done ainda podem alterar um item ignorado que permaneça no Project:
aplique exclusão por label se a regra oferecer esse filtro; caso contrário, desative
a regra conflitante e deixe o script executar essa transição para Issues elegíveis.
Nenhuma configuração remota foi alterada nesta implementação.

Não aplicar labels/editar os mesmos itens simultaneamente a uma escrita em andamento:
a API não oferece transação atômica entre consulta de labels e atualização do Project.
Referência: https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically

## Controles e dry-run revisados

A escrita exige simultaneamente `apply=true` e a variável de repositório
`PROJECT_AUTOMATION_ENABLED=true`. Se apply for true e a variável não for exatamente
true, o script termina com erro antes de consultar ou modificar o Project.
Com apply=false, continua somente leitura, independentemente da variável, e aceita
o token com read:project. Não habilite escrita antes de revisar o novo dry-run.

Na execução manual de **Project 3**, `issue_number` é opcional. Vazio analisa todas
as Issues; um inteiro positivo seleciona somente aquela Issue do MediaTrack.
Não aceita URL, nome de outro repositório ou expressão de shell. Números são locais
ao repositório: 25 significa exclusivamente a Issue 25 do MediaTrack. Issue inexistente
ou resposta de outro repositório interrompe a execução antes de qualquer escrita.
O script pode consultar a lista completa para localizar a Issue, mas só propõe/aplica
ações à selecionada. CLI equivalente somente de leitura:

```text
python scripts/project_automation.py --issue-number 25
```

O relatório mostra owner, número e URL retornados pelo Project, repositório permitido,
campo Status, opções e IDs técnicos. Valida owner/número/URL antes de continuar.
Para cada Issue, mostra estado aberta/fechada, Status atual, desejado e ação:
nenhuma, adicionar ou atualizar. Ausente significa que a Issue não possui item no
Project; sem Status significa que o item existe mas o campo não está preenchido.
Não foram consultados novamente os itens reais durante esta alteração local.

O Status atual é recuperado com fieldValueByName. Estado igual não gera mutation.
A resposta de addProjectV2ItemById também é examinada: se uma automação nativa já
criou o item e definiu o Status correto, não há atualização adicional. A API reutiliza
o item por contentId, sem criar uma segunda tarefa. Execuções do workflow permanecem
serializadas. Uma alteração manual simultânea entre leitura e escrita não tem garantia
de compare-and-swap pela API; evite editar os mesmos cards durante a reconciliação.

## Política de In Review

Não criar, renomear ou remover opções do Project. Não mover automaticamente uma Issue
para In Review. Se uma Issue aberta já estiver em In Review, preservar essa escolha
manual mesmo sem PR ativa, com observação explícita no relatório. Issue fechada vai
para Done, inclusive quando estava em In Review. Reaberta a partir de Done segue a
política inicial: In Progress com PR ativa reconhecida; caso contrário Todo.

## Próxima validação

Enviar as alterações pelo procedimento manual do mantenedor e executar novamente
apply=false, mantendo PROJECT_AUTOMATION_ENABLED=false e read:project. Conferir os
itens ausentes e estados propostos; repetir o dry-run. Somente após revisão, preparar
uma Issue temporária e usar issue_number para o teste controlado. Não executar escrita
global como primeiro teste. Nenhuma mutação real foi realizada na validação local;
os testes de escrita utilizam exclusivamente respostas simuladas.
