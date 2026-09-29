import csv
import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from integracoes.dvd_dataset import importar

class Command(BaseCommand):
    help = 'Importa DVDs do SQL do grupo via ORM, sem executar SQL nem cadastrar estoque.'
    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=None)
        parser.add_argument('--lote', type=int, default=500)
        parser.add_argument('--legado-csv', action='store_true', help='Importação auxiliar antiga; não identifica DVDs por EAN.')
    def handle(self, *args, **options):
        path = options['arquivo'] or (None if options['legado_csv'] else settings.DVD_DATASET_PATH)
        if not path:
            raise CommandError('Informe --arquivo para o CSV legado.')
        if not 1 <= options['lote'] <= 2000:
            raise CommandError('Lote deve estar entre 1 e 2000.')
        try:
            if options['legado_csv']:
                from integracoes.movies_dataset import importar as importar_legado
                result = importar_legado(path, options['lote'])
            else:
                result = importar(path)
        except (OSError, ValueError, csv.Error) as exc:
            raise CommandError(f'Não foi possível importar a base: {exc}') from exc
        self.stdout.write(json.dumps(result))
