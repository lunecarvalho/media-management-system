import logging
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger('mediatrack')


def business_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response({'erro': {'codigo': 'protegido', 'detalhes': 'Registro vinculado a outros dados; remoção não permitida.'}}, status=409)
    if isinstance(exc, IntegrityError):
        logger.warning('Conflito de integridade em operação de acervo.')
        return Response({'erro': {'codigo': 'conflito', 'detalhes': 'Dados em conflito. Recarregue e confira os códigos.'}}, status=409)
    if isinstance(exc, ValidationError):
        return Response({'erro': {'codigo': 'validacao', 'detalhes': getattr(exc, 'message_dict', exc.messages)}}, status=400)
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {'erro': {'codigo': str(response.status_code), 'detalhes': response.data}}
    return response
