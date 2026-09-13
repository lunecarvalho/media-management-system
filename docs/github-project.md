# Kanban existente

Único destino: https://github.com/users/lunecarvalho/projects/3.
Issues de lunecarvalho/media-management-system são as tarefas.

Não foi possível consultar o Project autenticado neste ambiente. Node ID, ID do
Status, opções e itens existentes não foram inventados. O script descobre esses
valores e os imprime antes de mutações; interrompe em caso de erro.

## Preferir automações nativas

Em Project #3 > Workflows, revisar auto-add com filtro
`repo:lunecarvalho/media-management-system is:issue`, item added -> Todo e
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
