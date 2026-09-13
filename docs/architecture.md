# Arquitetura e preservação de dados

## Modelos e regras

Produto armazena título, mídia, EAN/UPC opcional único, ano, autoria/direção, categoria protegida, descrição, editora/gravadora/distribuidora e metadados/identificadores externos. A autoria está no campo combinado artista_diretor; dados adicionais podem permanecer no JSON de metadados.

Exemplar tem código interno único, Produto obrigatório, conservação, preço não negativo, localização, status, responsável e datas. Vários exemplares compartilham um Produto e, portanto, o mesmo EAN/UPC. O alias Item mantém compatibilidade de código; não representa outra tabela.

Movimentacao registra evento, responsável, data e snapshots anterior/novo. Relações protegidas impedem a perda automática do histórico. A exclusão funcional cancela o exemplar; a venda deve ser cancelada antes dessa operação. Categoria não pode ser removida enquanto referenciada. Perfil associa usuário, tipo e ativo.

acervo/services.py centraliza alterações do estoque em transações e valida estados, conflitos de edição, preços e auditoria. HTML, API e Admin passam pelos serviços nas operações implementadas. Movimentações no Admin são somente leitura.

## Permissões

| Perfil ativo | Ações |
| --- | --- |
| Funcionário | Consultar e editar acervo, importação e pesquisa de metadados |
| Administrador | Ações anteriores, categorias e cancelamento/exclusão funcional |
| Proprietário | Ações anteriores e gestão de usuários |

Usuário anônimo não acessa páginas internas nem API. Perfil inativo bloqueia ações protegidas, inclusive para superusuário com perfil explicitamente inativo. Superusuário sem perfil é permitido para administração inicial. O Admin também mantém os requisitos nativos de staff/permissões Django. Login e health check permanecem públicos; logout é POST.

API usa autenticação por sessão e CSRF, paginação e envelope de erro. /api/itens/ preserva a rota de compatibilidade; /api/exemplares/ e /api/produtos/ expõem a nova arquitetura.

## Migrações

- acervo/0002_produto_exemplar: renomeia Item para Exemplar e o código para codigo_interno; cria Produto, copia metadados, vincula e só então remove os campos antigos.
- acervo/0003: validações e constraints de ano/preço.
- acervo/0004: registros de pré-visualização/importação CSV.
- movimentacoes/0002: tipos de eventos, snapshots e relações protegidas.
- integracoes/0001 e 0002: controle de requisições externas e FilmeReferencia.

IDs de exemplares e vínculos de movimentações são preservados. A migração cria um Produto por registro legado, sem deduplicar silenciosamente metadados. O código legado é preservado como código interno e copiado para EAN; confirme a semântica desses códigos antes de utilizar o catálogo comercial.

A migração de dados não tem reversão automática. Antes de aplicar no acervo real: faça backup consistente, teste sua restauração, examine anos/preços inválidos e execute migrate numa cópia. Constraints podem recusar dados legados inválidos: corrija com revisão humana, sem apagar registros. Valide contagens, IDs e vínculos após a migração. Não foi executada migração no banco real durante esta retomada.

## Consultas e auditoria

Dashboard consulta totais de Produtos/Exemplares, status, valor de disponíveis/reservados e últimas movimentações. Os indicadores são atualizados na requisição da página. Listagens usam paginação.

Leitor funciona como teclado: código interno abre exemplar; EAN mostra Produto e exemplares; desconhecido oferece pesquisa/cadastro. A seleção explícita do tipo resolve colisões entre códigos internos e comerciais. Não existe detecção física do dispositivo.
