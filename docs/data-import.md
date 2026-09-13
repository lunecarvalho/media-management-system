# Importação e fontes auxiliares

## CSV do acervo

Use examples/acervo.csv como modelo. Fluxo: upload UTF-8 separado por vírgulas, validação e prévia, erros/duplicados por linha, confirmação POST e relatório. Limites: 1 MiB e 500 linhas. A prévia pertence ao usuário que a criou e expira em 24 horas.

EAN existente reutiliza Produto sem sobrescrever seus metadados. EAN repetido pode cadastrar várias unidades com códigos internos diferentes. Código interno existente com dados equivalentes é ignorado; dados conflitantes bloqueiam a importação. Categoria deve existir. Linhas inválidas impedem a confirmação do lote inteiro. A confirmação é transacional e não pode ser aplicada duas vezes. Revise todos os erros antes de reenviar.

## MusicBrainz

integracoes/musicbrainz.py pesquisa edições de CDs, usa timeout de conexão/leitura, User-Agent configurável, cache de uma hora e controle no banco entre requisições (intervalo de 1,1 segundo). Indisponibilidade é apresentada ao usuário; testes usam mocks, sem acessar o serviço.

Configure MUSICBRAINZ_USER_AGENT com identificação e contato reais. Pesquisa apresenta resultados para seleção e confirmação; somente então os metadados e identificadores são associados ao Produto. O cadastro de Exemplar continua separado. O cache padrão é local a cada processo; o controle de frequência usa o banco compartilhado.

## Movies Dataset

Fonte opcional: https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset.
Obtenha o arquivo movies_metadata.csv diretamente no Kaggle, observando seus termos/licença e eventual autenticação. Não inclua credenciais Kaggle nem o dataset no Git.

Configure MOVIES_DATASET_PATH com o caminho local e execute:

```text
python manage.py importar_filmes
python manage.py importar_filmes --arquivo CAMINHO_DO_CSV --lote 500
```

O comando processa lotes, informa processados/importados/ignorados/inválidos e ignora identificadores já importados. Reexecutar não duplica o catálogo; não atualiza silenciosamente registros existentes.

FilmeReferencia é catálogo auxiliar no banco operacional, separado de Produto/Exemplar. Busca por título/título original, ano e IDs IMDb/TMDB. Metadados incluem descrição, gêneros, idioma, países e produtoras quando disponíveis. Resultados exigem seleção e confirmação, inclusive antes de enriquecer um Produto existente. Dados obrigatórios não disponíveis precisam ser preenchidos pelo usuário.

EAN/UPC de DVDs nunca é inferido desse dataset. A ausência do arquivo não impede inicialização; apenas deixa indisponível seu conteúdo até a ingestão. Testes usam amostras pequenas. Novas fontes podem ser adicionadas na camada integracoes.
