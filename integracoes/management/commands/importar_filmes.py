import csv
import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from integracoes.movies_dataset import importar

class Command(BaseCommand):
    help = 'Ingere movies_metadata.csv em lotes, sem alterar Produto ou Exemplar.'
    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=None)
        parser.add_argument('--lote', type=int, default=500)
    def handle(self, *args, **options):
        path = options['arquivo'] or settings.MOVIES_DATASET_PATH
        if not path:
            raise CommandError('Defina MOVIES_DATASET_PATH ou --arquivo.')
        if not 1 <= options['lote'] <= 2000:
            raise CommandError('Lote deve estar entre 1 e 2000.')
        try:
            result = importar(path, options['lote'])
        except (OSError, ValueError, csv.Error) as exc:
            raise CommandError('Não foi possível ler o dataset; confira caminho, UTF-8 e cabeçalhos.') from exc
        self.stdout.write(json.dumps(result))
