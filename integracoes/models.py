from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from acervo.validators import validar_ano

class LimiteAPI(models.Model):
    nome = models.CharField(max_length=40, primary_key=True)
    ultima = models.DateTimeField(null=True)


class FilmeReferencia(models.Model):
    tmdb_id = models.BigIntegerField(unique=True, validators=[MinValueValidator(1)])
    imdb_id = models.CharField(max_length=30, blank=True, db_index=True, validators=[RegexValidator(r'^tt[0-9]+$')])
    titulo = models.CharField(max_length=300, db_index=True)
    titulo_original = models.CharField(max_length=300, db_index=True)
    ano = models.IntegerField(null=True, blank=True, validators=[validar_ano], db_index=True)
    descricao = models.TextField(blank=True)
    metadados = models.JSONField(default=dict, blank=True)
    origem = models.CharField(max_length=100, default='Kaggle:rounakbanik/the-movies-dataset')
