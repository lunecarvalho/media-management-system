# MediaTrack

Sistema Django para o acervo de CDs e DVDs de um sebo, desenvolvido como recurso para a disciplina de Projeto Integrador II da UNIVESP.

## Estado atual

Python 3.14 e Django 5.2 LTS. Produto representa a edição comercial; Exemplar representa cada unidade física. Existem autenticação por sessão, permissões por perfil ativo, histórico transacional, dashboard consultado no banco, paginação, API REST, importação CSV com confirmação e consulta por código interno ou EAN/UPC.

MusicBrainz fornece sugestões para CDs com seleção explícita. O Movies Dataset é um catálogo auxiliar opcional para filmes, separado do banco operacional. Não identifica códigos de barras físicos.

Produção preparada para Gunicorn/WhiteNoise em Docker no Elastic Beanstalk, com PostgreSQL no RDS e TLS verificado. Nenhuma infraestrutura foi criada e nenhum deploy foi executado. Docker e PostgreSQL real ainda precisam da validação externa descrita na documentação.

## Documentação

- [Instalação e desenvolvimento](DEVELOPMENT.md)
- [Arquitetura, permissões e migrações](docs/architecture.md)
- [CSV e fontes de metadados](docs/data-import.md)
- [Docker, AWS e operação](docs/aws.md)
- [GitHub Project pessoal #3](docs/github-project.md)

O CI mantém SQLite e PostgreSQL e valida o pacote Docker após os testes. O CD é somente manual, bloqueado por padrão e depende do CI. O próximo marco é validar a imagem e o PostgreSQL no CI, revisar a migração com backup e preparar um ambiente de homologação após autorização.
