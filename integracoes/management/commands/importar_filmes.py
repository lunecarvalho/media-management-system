import csv
import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from integracoes.dvd_dataset import importar, preflight, simular

class Command(BaseCommand):
    help = 'Importa DVDs do SQL do grupo via ORM, sem executar SQL nem cadastrar estoque.'
    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=None)
        parser.add_argument('--lote', type=int, default=500)
        parser.add_argument('--legado-csv', action='store_true', help='Importação auxiliar antiga; não identifica DVDs por EAN.')
        parser.add_argument('--dry-run', action='store_true', help='Valida o SQL somente em memória, sem consultar ou alterar o banco.')
        parser.add_argument('--confirmar', action='store_true',
                            help='Executa preflight, solicita confirmação e importa atomicamente.')
        parser.add_argument('--confirmar-banco', default=None,
                            help='Nome esperado do banco; obrigatório com --confirmar.')
    def handle(self, *args, **options):
        path = options['arquivo'] or (None if options['legado_csv'] else settings.DVD_DATASET_PATH)
        if not path:
            raise CommandError('Informe --arquivo para o CSV legado.')
        if not 1 <= options['lote'] <= 2000:
            raise CommandError('Lote deve estar entre 1 e 2000.')
        try:
            if options['dry_run'] and options['legado_csv']:
                raise CommandError('--dry-run não pode ser usado com --legado-csv.')
            if options['confirmar'] and options['legado_csv']:
                raise CommandError('--confirmar não pode ser usado com --legado-csv.')
            if options['confirmar'] and not options['confirmar_banco']:
                raise CommandError('--confirmar exige --confirmar-banco.')
            if options['confirmar'] and options['dry_run']:
                raise CommandError('--confirmar não pode ser usado com --dry-run.')
            if options['dry_run']:
                result = simular(path)
            elif options['confirmar']:
                result = preflight(path, expected_database=options['confirmar_banco'])
                if result['conflitos_outra_origem']:
                    raise CommandError('Preflight encontrou conflitos com outras origens; nenhuma alteração realizada.')
                if result['invalidos'] or result['duplicados_conflitantes']:
                    raise CommandError('Preflight encontrou registros inválidos; nenhuma alteração realizada.')
                self.stdout.write(json.dumps(result))
                confirmation = input('Digite CONFIRMAR para executar a importação: ')
                if confirmation != 'CONFIRMAR':
                    raise CommandError('Importação cancelada; nenhuma alteração realizada.')
                result = importar(path, strict=True)
            elif options['legado_csv']:
                from integracoes.movies_dataset import importar as importar_legado
                result = importar_legado(path, options['lote'])
            else:
                result = importar(path)
        except (OSError, ValueError, ValidationError, csv.Error) as exc:
            raise CommandError(f'Não foi possível importar a base: {exc}') from exc
        self.stdout.write(json.dumps(result))
