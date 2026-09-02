from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):
    """Perfil estendido do usuário"""
    
    TIPO_CHOICES = (
        ('proprietario', 'Proprietário'),
        ('administrador', 'Administrador'),
        ('funcionario', 'Funcionário'),
    )
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='funcionario')
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Perfis'
    
    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.get_tipo_display()})"
