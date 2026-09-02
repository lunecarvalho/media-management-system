from django.db import models
from django.contrib.auth.models import User
from acervo.models import Item


class Movimentacao(models.Model):
    """Registro de movimentação de item - venda, cadastro, edição, etc"""
    
    TIPO_CHOICES = (
        ('cadastro', 'Cadastro'),
        ('venda', 'Venda'),
        ('reserva', 'Reserva'),
        ('edicao', 'Edição'),
        ('entrada', 'Entrada'),
        ('alteracao_status', 'Alteração de Status'),
    )
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='movimentacoes')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    data = models.DateTimeField(auto_now_add=True)
    detalhes = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'Movimentações'
        ordering = ['-data']
    
    def __str__(self):
        return f"{self.item.titulo} - {self.get_tipo_display()}"
