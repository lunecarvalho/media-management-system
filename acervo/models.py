from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from .validators import validar_ano, validar_codigo

TIPOS = (('CD', 'CD'), ('DVD', 'DVD'))


class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Categorias'
        ordering = ['nome', 'pk']

    def __str__(self):
        return self.nome


class Produto(models.Model):
    tipo = models.CharField(max_length=10, choices=TIPOS)
    titulo = models.CharField(max_length=200)
    artista_diretor = models.CharField(max_length=200)
    ean = models.CharField(max_length=20, unique=True, null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    ano = models.IntegerField(null=True, blank=True, validators=[validar_ano])
    gravadora_distribuidora = models.CharField(max_length=200, blank=True)
    descricao = models.TextField(blank=True)
    identificadores = models.JSONField(default=dict, blank=True)
    metadados = models.JSONField(default=dict, blank=True)
    origem = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['titulo', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(ano__gte=1) | models.Q(ano__isnull=True), name='produto_ano_positivo')]

    def clean(self):
        self.ean = self.ean.strip() if self.ean else None

    def __str__(self):
        return f'{self.titulo} ({self.tipo})'


class Exemplar(models.Model):
    TIPO_CHOICES = TIPOS
    ESTADO_CHOICES = (('novo', 'Novo'), ('excelente', 'Excelente'), ('bom', 'Bom'), ('regular', 'Regular'), ('ruim', 'Ruim'))
    STATUS_CHOICES = (('disponivel', 'Disponível'), ('reservado', 'Reservado'), ('vendido', 'Vendido'), ('cancelado', 'Cancelado'))
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='exemplares')
    codigo_interno = models.CharField(max_length=40, unique=True, validators=[validar_codigo])
    estado_conservacao = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='bom')
    preco = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    localizacao = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disponivel')
    usuario_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Exemplares'
        ordering = ['-data_cadastro', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(preco__gte=0) | models.Q(preco__isnull=True), name='exemplar_preco_nao_negativo')]

    # Compatibilidade de apresentação com os templates e clientes legados.
    @property
    def titulo(self): return self.produto.titulo
    @property
    def tipo(self): return self.produto.tipo
    @property
    def artista_diretor(self): return self.produto.artista_diretor
    @property
    def categoria(self): return self.produto.categoria
    @property
    def ano(self): return self.produto.ano
    @property
    def descricao(self): return self.produto.descricao
    @property
    def gravadora_distribuidora(self): return self.produto.gravadora_distribuidora
    @property
    def codigo_barras(self): return self.codigo_interno

    def __str__(self):
        return f'{self.codigo_interno} — {self.produto}'


# Alias temporário para imports e rotas existentes. Não cria outra tabela.
Item = Exemplar


class ImportacaoCSV(models.Model):
    import uuid
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criado = models.DateTimeField(auto_now_add=True)
    conteudo = models.TextField()
    confirmado = models.BooleanField(default=False)
    resultado = models.JSONField(default=dict)
