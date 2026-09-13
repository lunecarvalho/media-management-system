from django.conf import settings
from django.db import models
from acervo.models import Exemplar


class Movimentacao(models.Model):
    TIPO_CHOICES = tuple((value, label) for value, label in [
        ('cadastro', 'Cadastro legado'), ('entrada', 'Entrada'), ('edicao', 'Edição'),
        ('alteracao_preco', 'Alteração de preço'), ('mudanca_localizacao', 'Mudança de localização'),
        ('reserva', 'Reserva'), ('cancelamento_reserva', 'Cancelamento de reserva'),
        ('venda', 'Venda'), ('cancelamento', 'Cancelamento'), ('alteracao_status', 'Alteração de status')])
    item = models.ForeignKey(Exemplar, on_delete=models.PROTECT, related_name='movimentacoes')
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data = models.DateTimeField(auto_now_add=True)
    anterior = models.JSONField(default=dict, blank=True)
    novo = models.JSONField(default=dict, blank=True)
    detalhes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Movimentações'
        ordering = ['-data', '-pk']

    def __str__(self):
        return f'{self.item} - {self.get_tipo_display()}'
