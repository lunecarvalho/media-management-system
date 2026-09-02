from django.db import models
from django.contrib.auth.models import User


class Categoria(models.Model):
    """Categoria ou gênero de itens (Rock, Drama, etc)"""
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Categorias'
    
    def __str__(self):
        return self.nome


class Item(models.Model):
    """Item do acervo - CD ou DVD"""
    
    TIPO_CHOICES = (
        ('CD', 'CD'),
        ('DVD', 'DVD'),
    )
    
    ESTADO_CHOICES = (
        ('novo', 'Novo'),
        ('excelente', 'Excelente'),
        ('bom', 'Bom'),
        ('regular', 'Regular'),
        ('ruim', 'Ruim'),
    )
    
    STATUS_CHOICES = (
        ('disponivel', 'Disponível'),
        ('reservado', 'Reservado'),
        ('vendido', 'Vendido'),
    )
    
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    artista_diretor = models.CharField(max_length=200)
    codigo_barras = models.CharField(max_length=20, unique=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    ano = models.IntegerField(blank=True, null=True)
    gravadora_distribuidora = models.CharField(max_length=200, blank=True)
    descricao = models.TextField(blank=True)
    estado_conservacao = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='bom')
    preco = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    localizacao = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disponivel')
    # capa = models.ImageField(upload_to='capas/', blank=True, null=True)  # Será adicionado após configurar Pillow
    
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    usuario_responsavel = models.ForeignKey(User, on_delete=models.PROTECT)
    
    class Meta:
        verbose_name_plural = 'Itens'
        ordering = ['-data_cadastro']
    
    def __str__(self):
        return f"{self.titulo} ({self.tipo})"
