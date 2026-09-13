"""Valida resposta já obtida do EB. Não acessa rede nem executa AWS CLI."""
import argparse
import json
from pathlib import Path


def validate(payload, application, environment, version=None):
    environments = payload.get('Environments', [])
    if len(environments) != 1:
        raise ValueError('Esperado exatamente um ambiente existente.')
    target = environments[0]
    if target.get('ApplicationName') != application or target.get('EnvironmentName') != environment:
        raise ValueError('Ambiente retornado não corresponde à aplicação/destino autorizado.')
    if target.get('Status') != 'Ready' or target.get('AbortableOperationInProgress'):
        raise ValueError('Ambiente não está pronto; não prosseguir com deploy.')
    if version is not None:
        if target.get('VersionLabel') != version or target.get('Health') != 'Green':
            raise ValueError('Versão esperada não está ativa e saudável; revisar operação e rollback.')
    return target.get('VersionLabel')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--application', required=True)
    parser.add_argument('--environment', required=True)
    parser.add_argument('--version')
    args = parser.parse_args()
    try:
        previous = validate(json.loads(args.file.read_text()), args.application, args.environment, args.version)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Validação EB falhou: {exc}\n')
    print(f'Ambiente validado; versão registrada: {previous}')
