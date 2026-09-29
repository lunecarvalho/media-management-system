<div align="center">

# 🎬 MediaTrack

Sistema web para **catalogação, organização e gerenciamento de CDs e DVDs**, desenvolvido com Django como parte do **Projeto Integrador II da UNIVESP**.

<br>

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-Deployment-FF9900?style=for-the-badge&logo=amazonwebservices&logoColor=white)

</div>

---

## Sobre o projeto

O **MediaTrack** foi criado para auxiliar na gestão do acervo de um sebo especializado em mídias físicas.

A aplicação permite administrar separadamente o **produto comercial** e seus **exemplares físicos**, possibilitando que diferentes unidades de um mesmo CD ou DVD compartilhem informações como título, artista, ano e código de barras, mantendo individualmente dados como estado de conservação, preço, localização e disponibilidade.

O projeto também explora conceitos de desenvolvimento web, APIs REST, bancos de dados relacionais, integração com serviços externos, testes automatizados, containers e CI/CD.

---

## Funcionalidades

- Cadastro e gerenciamento de CDs e DVDs
- Identificação por código interno e EAN/UPC
- Controle individual de exemplares
- Pesquisa e paginação do acervo
- Autenticação e controle de permissões
- Dashboard com informações do banco de dados
- Histórico de movimentações
- Importação de dados via CSV
- API REST
- Integração com MusicBrainz para metadados de CDs
- Identificação de DVDs pela base EAN/UPC local do grupo
- Busca alternativa de CDs por título e artista
- Cadastro manual com preservação do EAN físico quando nenhuma fonte encontra o item
- Testes automatizados
- Ambiente preparado para Docker
- CI/CD com GitHub Actions

---

## Modelo do acervo

O MediaTrack separa o conceito de produto de suas unidades físicas:

```text
Produto
│
├── Título
├── Tipo de mídia
├── EAN / UPC
├── Ano
├── Artista / Diretor
└── Metadados externos
        │
        ├── Exemplar #1
        ├── Exemplar #2
        └── Exemplar #3
```

Cada **Produto** representa uma edição comercial, enquanto cada **Exemplar** representa uma unidade física existente no acervo.

Isso permite, por exemplo, que duas cópias do mesmo DVD possuam preços, estados de conservação e localizações diferentes.

---

## Tecnologias

| Área | Tecnologias |
|---|---|
| Backend | Python 3.14 · Django 5.2 LTS |
| API | Django REST Framework |
| Banco de dados | SQLite para desenvolvimento/testes · PostgreSQL em produção |
| Frontend | Django Templates · HTML · CSS · JavaScript |
| Integrações | MusicBrainz API · base local de DVDs por EAN |
| Container | Docker |
| Servidor | Gunicorn |
| Arquivos estáticos | WhiteNoise |
| CI/CD | GitHub Actions |
| Cloud | AWS Elastic Beanstalk · Amazon RDS |
| Design | Figma |
| Versionamento | Git · GitHub |

---

## Integrações

### CDs → MusicBrainz

Pesquisa por título, artista ou EAN/UPC, aceitando somente edições cujo formato seja
explicitamente CD. Os metadados selecionados são revisados antes do cadastro.

### DVDs → base EAN/UPC local do grupo

O arquivo `datasets/bd_model-criacao.sql` popula o model Django `FilmeReferencia`
com EAN/UPC, título, diretor e ano. A aplicação consulta esse model no mesmo banco
operacional; não executa o arquivo SQL durante leituras.

No leitor: **acervo cadastrado → base local de DVDs → MusicBrainz/CD → cadastro manual**.
Um DVD encontrado localmente não gera requisição ao MusicBrainz. Sem resultado,
o EAN permanece no formulário e o usuário escolhe o tipo e preenche os dados.

Após disponibilizar o arquivo e aplicar as migrações, execute `python manage.py importar_filmes`.
O importador lê `datasets/bd_model-criacao.sql` via ORM, sem executar o SQL diretamente,
e é idempotente: EANs com os mesmos dados são ignorados e referências alteradas são
atualizadas. Outros arquivos em `datasets/` permanecem ignorados pelo Git.
Detalhes, reimportação e compatibilidade legada: [guia de importação](docs/data-import.md).

### Fluxo de identificação por código de barras

```text
Código de barras
   ↓
Item já existe no acervo?
   ↓ não
Base local de DVDs
   ↓ não encontrado
MusicBrainz (CD)
   ↓ não encontrado
Busca por título/artista
   ↓
Cadastro manual
```

CDs são consultados no MusicBrainz; DVDs são consultados na base local do projeto.
Quando a identificação automática de um CD falha, o usuário pode pesquisar por título,
artista ou ambos e selecionar explicitamente uma edição compatível com CD. O EAN físico
informado no leitor permanece no cadastro, separado do barcode eventualmente retornado
pela fonte externa.

### CD não encontrado pelo EAN

No leitor, use **Buscar CD por título/artista** para pesquisar explicitamente no
MusicBrainz. Informe título, artista ou ambos e selecione a edição correta.
Somente edições compostas exclusivamente por CDs são aceitas. O EAN físico
permanece no cadastro; o barcode da fonte fica em `metadados.barcode_musicbrainz`
e o release em `identificadores.musicbrainz_release_id`. Nenhum produto é salvo
antes da confirmação. Sem resultados ou com a fonte indisponível, o cadastro
manual continua disponível com o EAN preenchido. DVDs mantêm a consulta local.

---

## Testes e qualidade

O projeto possui uma suíte automatizada que cobre componentes da aplicação e configurações de produção.

O pipeline de **Continuous Integration** executa validações utilizando:

- SQLite
- PostgreSQL
- testes automatizados
- verificações do Django
- validação do pacote de produção
- build Docker

O deploy permanece **manual e protegido**, evitando a criação ou alteração acidental de infraestrutura.

---

## Arquitetura de produção

A arquitetura preparada para produção segue o fluxo:

```text
GitHub
   │
   ▼
GitHub Actions
   │
   ▼
AWS Elastic Beanstalk
   │
   ▼
Docker + Gunicorn
   │
   ▼
Django
   │
   ▼
Amazon RDS PostgreSQL
```

A conexão com o PostgreSQL em produção é preparada para utilizar **TLS com verificação de certificado**.

> [!NOTE]
> A infraestrutura AWS ainda não foi provisionada e nenhum deploy de produção foi executado.

---

## Documentação

A documentação técnica detalhada está organizada separadamente:

- [Instalação e ambiente de desenvolvimento](DEVELOPMENT.md)
- [Arquitetura, permissões e migrações](docs/architecture.md)
- [Importação CSV e fontes de metadados](docs/data-import.md)
- [Docker e AWS](docs/aws.md)
- [Operações AWS, homologação e rollback](docs/aws-operations.md)
- [Automação do GitHub Project](docs/github-project.md)

---

## Executando localmente

Consulte o guia completo de configuração do ambiente:

➡️ **[DEVELOPMENT.md](DEVELOPMENT.md)**

---

## Status do projeto

O MediaTrack está em desenvolvimento ativo.

Atualmente, a aplicação possui a arquitetura principal, autenticação, gerenciamento do acervo, API REST, integrações, testes automatizados e pipeline de CI configurados.

As próximas etapas envolvem a preparação do ambiente de homologação e a validação da infraestrutura AWS.

---

## Contexto acadêmico

Este projeto foi desenvolvido como recurso da disciplina de **Projeto Integrador II da UNIVESP**, aplicando conceitos de desenvolvimento de software, banco de dados, integração de sistemas e gestão de projetos em uma solução voltada a um cenário real de gerenciamento de acervo.

---
