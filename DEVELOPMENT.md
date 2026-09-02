# MediaTrack - Acervo Físico

Sistema web de gerenciamento de acervo de CDs e DVDs para sebos. Desenvolvido com Django, PostgreSQL, HTML5, CSS3 e JavaScript vanilla.

## Características

- ✅ Interface moderna e profissional
- ✅ Gerenciamento completo de itens (CDs e DVDs)
- ✅ Dashboard com estatísticas em tempo real
- ✅ Integração com leitor de código de barras USB
- ✅ Histórico de movimentações
- ✅ Categorização de itens
- ✅ Gerenciamento de usuários
- ✅ API REST com Django REST Framework
- ✅ Containerizado com Docker
- ✅ Suporte a PostgreSQL
- ✅ Acessibilidade WCAG

## Stack Tecnológico

### Backend
- Python 3.11+
- Django 4.2
- Django REST Framework
- PostgreSQL 15

### Frontend
- HTML5
- CSS3
- JavaScript Vanilla
- Django Templates

### DevOps
- Docker & Docker Compose
- Git
- GitHub Actions (CI/CD)

## Instalação Local

### Pré-requisitos

- Python 3.11+
- PostgreSQL 15+ (ou usar Docker Compose)
- Git
- pip ou virtualenv

### 1. Clonar repositório

```bash
git clone https://github.com/lunecarvalho/media-management-system
cd media-management-system
```

### 2. Criar ambiente virtual

```bash
python -m venv venv

# No Windows
venv\Scripts\activate

# No Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar .env com suas configurações locais
# Importante: Mude SECRET_KEY e as credenciais do banco
```

O arquivo `.env` nunca deve ser commitado (já está no `.gitignore`). Use `.env.example` apenas como referência de quais variáveis existem.

**Variáveis de ambiente disponíveis:**

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | Sim (produção) | Chave secreta do Django. Gere uma nova e nunca reutilize a de exemplo. |
| `DEBUG` | Não (padrão `True`) | Deve ser `False` em produção. |
| `ALLOWED_HOSTS` | Sim (produção) | Domínios separados por vírgula. |
| `DATABASE_URL` | Não | URL completa do Postgres (Render/Supabase). Tem prioridade sobre `DB_*`. |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Não | Alternativa ao `DATABASE_URL` (ex: Postgres local via Docker). Sem essas variáveis, o projeto usa SQLite automaticamente. |
| `CORS_ALLOWED_ORIGINS` | Não | Origens permitidas, separadas por vírgula. |
| `CSRF_TRUSTED_ORIGINS` | Sim (produção, se atrás de proxy/domínio próprio) | Domínios confiáveis para POST, separados por vírgula. |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | Não | Ajustes finos de segurança quando `DEBUG=False`. |
| `MUSICBRAINZ_API_URL`, `TMDB_API_KEY` | Não | Integrações futuras com APIs externas. |

### 5. Executar migrações do banco

```bash
python manage.py migrate
```

### 6. Criar superusuário (Admin)

```bash
python manage.py createsuperuser
```

### 7. Coletar arquivos estáticos (opcional em desenvolvimento)

```bash
python manage.py collectstatic
```

### 8. Executar servidor de desenvolvimento

```bash
python manage.py runserver
```

Acesse: http://localhost:8000/

Admin: http://localhost:8000/admin/

## Usando Docker

### 1. Requisitos

- Docker
- Docker Compose

### 2. Executar com Docker Compose

```bash
docker-compose up -d
```

Isso iniciará:
- PostgreSQL na porta 5432
- Django na porta 8000

O Django realizará automaticamente:
- Migrações do banco
- Coleta de arquivos estáticos

### 3. Acessar a aplicação

- Frontend: http://localhost:8000/
- Admin: http://localhost:8000/admin/

### 4. Parar os containers

```bash
docker-compose down
```

## Deploy no Render

O projeto está pronto para rodar no Render com PostgreSQL (ex: Supabase) como banco de dados. Nenhuma credencial de produção deve ser colocada no repositório — configure-as diretamente no painel do Render, em **Environment**:

| Variável | Valor esperado |
|---|---|
| `SECRET_KEY` | Chave secreta gerada especificamente para produção (nunca reutilize a de desenvolvimento). |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | Domínio do serviço no Render (ex: `mediatrack.onrender.com`). |
| `DATABASE_URL` | URL de conexão do Postgres/Supabase, fornecida pelo próprio serviço de banco. |
| `CSRF_TRUSTED_ORIGINS` | `https://` + domínio do serviço no Render. |
| `CORS_ALLOWED_ORIGINS` | Domínios do frontend que podem consumir a API, se aplicável. |
| `MUSICBRAINZ_API_URL`, `TMDB_API_KEY` | Somente se as integrações externas forem utilizadas. |

Comando de build sugerido: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`.
Comando de start sugerido: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`.

## Estrutura do Projeto

```
mediatrack/
├── config/                 # Configurações do Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── acervo/                 # App de gerenciamento de itens
│   ├── models.py
│   ├── views.py
│   └── admin.py
├── movimentacoes/          # App de histórico de transações
│   ├── models.py
│   └── admin.py
├── categorias/             # App de categorias
├── usuarios/               # App de usuários
├── api/                    # APIs REST
│   ├── serializers.py
│   └── views.py
├── templates/              # Templates Django
│   ├── base.html
│   └── dashboard.html
├── static/                 # Arquivos estáticos
│   ├── css/
│   │   ├── design-system.css
│   │   ├── layout.css
│   │   └── dashboard.css
│   └── js/
│       └── app.js
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Roadmap

- [x] Estrutura inicial do Django
- [x] Design system CSS
- [x] Layout com sidebar
- [x] Dashboard com stats
- [x] CRUD de itens
- [x] Integração com leitor de código de barras
- [x] APIs REST completas
- [x] Sistema de autenticação avançado
- [ ] Importação de CSV
- [ ] Integração com MusicBrainz
- [ ] Testes automatizados
- [ ] Deploy no Render
- [ ] CI/CD com GitHub Actions

## Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está sob licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contato

Para dúvidas ou sugestões, abra uma issue no repositório.

---

**Desenvolvido com ❤️ para gerenciar acervos de forma profissional e acessível.**
