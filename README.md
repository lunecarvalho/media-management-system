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
- Consulta auxiliar de metadados de filmes
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
| Banco de dados | SQLite · PostgreSQL |
| Frontend | Django Templates · HTML · CSS · JavaScript |
| Container | Docker |
| Servidor | Gunicorn |
| Arquivos estáticos | WhiteNoise |
| CI/CD | GitHub Actions |
| Cloud | AWS Elastic Beanstalk · Amazon RDS |
| Design | Figma |
| Versionamento | Git · GitHub |

---

## Integrações

### MusicBrainz

Utilizado para sugerir metadados de CDs. Os resultados são apresentados para seleção antes de serem associados ao produto.

### Movies Dataset

Utilizado como catálogo auxiliar de metadados cinematográficos.

O dataset é independente do banco operacional do MediaTrack e **não é utilizado como catálogo de códigos EAN/UPC**.

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