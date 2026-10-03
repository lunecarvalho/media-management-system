# Importação e fontes auxiliares

## CSV do acervo

Use examples/acervo.csv como modelo. Fluxo: upload UTF-8 separado por vírgulas, validação e prévia, erros/duplicados por linha, confirmação POST e relatório. Limites: 1 MiB e 500 linhas. A prévia pertence ao usuário que a criou e expira em 24 horas.

EAN existente reutiliza Produto sem sobrescrever seus metadados. EAN repetido pode cadastrar várias unidades com códigos internos diferentes. Código interno existente com dados equivalentes é ignorado; dados conflitantes bloqueiam a importação. Categoria deve existir. Linhas inválidas impedem a confirmação do lote inteiro. A confirmação é transacional e não pode ser aplicada duas vezes. Revise todos os erros antes de reenviar.

## Arquitetura de identificação

- **CD → MusicBrainz**, somente com formato CD confirmado na resposta.
- **DVD → base EAN/UPC local do grupo**, importada em `FilmeReferencia`.
- **Não encontrado → cadastro manual**, mantendo EAN/UPC, sem inventar metadados.

O leitor em modo teclado e a consulta HTML verificam primeiro produto/exemplar já
cadastrado, depois a base de DVDs e por último MusicBrainz. A busca assíncrona de um
código comercial solicita essa sequência automaticamente. Não é preciso escolher
CD/DVD antes da leitura. O modo interno nunca consulta essas fontes.

A API de código mantém a consulta local por padrão (acervo + DVDs); `metadados=1`
habilita o fallback MusicBrainz. Produto/exemplar cadastrado sempre tem prioridade.
A tela de pesquisa de metadados continua permitindo título/artista para CDs e
EAN/título/ano para DVDs; um EAN conhecido da base de DVDs tem prioridade também ali.

## Carregar a base de DVDs

Fonte: `datasets/bd_model-criacao.sql`, fornecida pelo grupo e versionada no
repositório. É a base auxiliar local de referências de DVDs; os demais arquivos
de `datasets/` permanecem ignorados pelo Git. O dataset não faz parte da imagem
Docker de produção nem do ZIP padrão de deploy do Elastic Beanstalk.
O runtime normal não executa esse SQL diretamente: o comando Django abaixo lê o
arquivo e persiste os dados via ORM. A aplicação funciona sem essa importação,
mas a identificação local dos DVDs dessa base fica indisponível. Quando desejada,
a importação é um procedimento operacional separado, com o arquivo disponibilizado
ao comando. Não é necessário nem recomendado executar o SQL diretamente.

```text
python manage.py migrate
python manage.py importar_filmes
python manage.py importar_filmes --arquivo CAMINHO_DO_SQL
```

`DVD_DATASET_PATH` substitui opcionalmente o caminho padrão. Em produção, execute o
comando em um processo operacional com as configurações/credenciais do banco alvo
e acesso ao arquivo (por exemplo, montagem somente leitura). Depois da importação,
o runtime não precisa do arquivo. Não há segundo banco nem tabela FILMES paralela.
O ORM utiliza SQLite no desenvolvimento e PostgreSQL em produção.

O model `FilmeReferencia` existente foi ampliado com `ean` único e `diretor`;
`tmdb_id` tornou-se opcional. A migração não apaga referências legadas.

| SQL | Django / cadastro |
| --- | --- |
| EanId | ean como texto, preservando zeros iniciais presentes no arquivo |
| tit | titulo |
| diretor | diretor / artista_diretor |
| ano | ano |

O comando aceita o formato inspecionado: UTF-8, comentários de linha, o cabeçalho
CREATE TABLE conhecido e um INSERT INTO FILMES por linha, com quatro valores na
ordem EanId, tit, diretor, ano. Aceita nomes dessas colunas na mesma ordem e aspas
SQL escapadas por duplicação. Não é um interpretador SQL genérico: comandos
inesperados abortam antes das gravações. Limite de arquivo: 16 MiB.

O relatório JSON informa `processados`, `criados`, `atualizados`, `ignorados`,
`invalidos` e erros por linha. Registros inválidos são relatados e os válidos são
importados. Uma falha operacional de banco reverte a transação inteira.

Reexecução: EAN idêntico com mesmos dados é ignorado; alterações de título, diretor
ou ano atualizam apenas a referência. Duplicatas divergentes dentro do mesmo arquivo
são reportadas, mantendo a primeira ocorrência válida. Uma referência de outra
origem com o mesmo EAN exige revisão manual. Não são criados ou alterados Produtos,
Exemplares, categorias ou movimentações pelo importador.

### Limitações da base

O arquivo inspecionado contém 137 EANs únicos. Não fornece capas, descrição,
gêneros, categoria, preço, localização ou estado físico. O usuário completa os
campos necessários e confirma o cadastro. A qualidade dos títulos, diretores,
anos e associações EAN é responsabilidade da fonte; não se inventam correções.
EAN/UPC aceita 8, 12 ou 13 dígitos, coerente com o leitor. Não há validação de dígito
verificador nem conversão automática entre UPC e EAN; zeros já perdidos na fonte
numérica não podem ser recuperados. A consulta compara o código textual exato.

## MusicBrainz para CDs

A pesquisa inclui `format:CD` e verifica `media[].format` na resposta. Só são aceitas
edições com todas as mídias explicitamente `CD`; vinil, digital, DVD, formatos
faltantes e edições mistas são descartados. Uma consulta por EAN exige que o código
retornado seja exatamente o solicitado. A política conservadora pode excluir
edições válidas com formato ausente, variantes não reconhecidas ou CD + DVD.

Formato da API: [documentação MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API/Search/ReleaseSearch).
O cliente mantém User-Agent configurável, timeout, cache de uma hora e controle
compartilhado no banco com intervalo de 1,1 segundo. Configure
`MUSICBRAINZ_USER_AGENT` com contato real. Os testes usam mocks, sem rede.

Resultados não encontrados oferecem cadastro manual. Indisponibilidade/timeout
são informados como falha de consulta, sem afirmar que o produto não existe;
é possível tentar novamente ou continuar manualmente mantendo o EAN.

## Pré-preenchimento e confirmação

Resultados selecionados ficam por até 30 minutos na sessão Django persistida no
banco, vinculados ao usuário, com no máximo 40 opções recentes. O pré-preenchimento
não depende de cache local de worker. Origem, identificadores e metadados vêm da
sessão no servidor, não de campos enviados pelo cliente. O formulário confirma tipo
e EAN da edição selecionada e continua exigindo categoria e dados do exemplar.
Se a seleção expirar, o EAN é mantido para preenchimento manual. Se o produto já
existir, ele é reutilizado sem sobrescrever seus metadados.

## Dataset CSV anterior e TMDB

`movies_metadata.csv` não participa mais da identificação ou da pesquisa principal
de DVDs. Seus registros, campos e serviço auxiliar foram preservados porque contêm
descrição, gêneros e identificadores ausentes na nova base. Para compatibilidade,
a ingestão antiga exige opção explícita:

```text
python manage.py importar_filmes --legado-csv --arquivo CAMINHO_DO_CSV --lote 500
```

O CSV legado não associa EAN nem cria estoque. O módulo `movies_dataset.py` permanece
isolado do leitor e da view principal; seus testes continuam ativos. As referências
legadas não são retornadas como DVDs da base do grupo.

`MOVIES_DATASET_PATH` deixou de configurar o comando padrão. `TMDB_API_KEY` foi
removida das configurações: não existe integração com API TMDB. IDs legados no
model foram preservados para não perder dados históricos.
