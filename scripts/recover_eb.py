"""Recuperação fixa: sem upload, criação de versão, migração ou rollback automático."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

APPLICATION = 'MediaTrack'
ENVIRONMENT = 'mediatrack-production'
ENVIRONMENT_ID = 'e-tt46mpr2kw'
REGION = 'sa-east-1'
ACCOUNT = '167529901671'
VERSION = 'mediatrack-53075e0d70d8ef688b0a2cf6fe808f3454e728a3-37460072449-1'
BUCKET = 'mediatrack-deploy-artifacts-167529901671'
KEY = f'mediatrack/{VERSION}.zip'
ETAG = '"e7695d75176619c6d0598dffc4088c2f"'


def aws(service, operation, *arguments, profile=None):
    command = ['aws', service, operation, *arguments, '--region', REGION,
               '--output', 'json', '--no-cli-pager', '--cli-connect-timeout', '10',
               '--cli-read-timeout', '30']
    if profile:
        command += ['--profile', profile]
    # Não repetir automaticamente a chamada de mutação, nem imprimir erros brutos.
    result = subprocess.run(command, capture_output=True, text=True, timeout=45,
                            env=dict(os.environ, AWS_MAX_ATTEMPTS='1'))
    if result.returncode:
        raise ValueError(f'Falha em {service}:{operation}; consultar diagnóstico sanitizado.')
    return json.loads(result.stdout or '{}')


def target(payload):
    items = payload.get('Environments', [])
    if len(items) != 1:
        raise ValueError('Destino ausente ou ambíguo.')
    item = items[0]
    if (item.get('ApplicationName'), item.get('EnvironmentName'), item.get('EnvironmentId')) != (
            APPLICATION, ENVIRONMENT, ENVIRONMENT_ID):
        raise ValueError('Destino diferente do aprovado.')
    return item


def production_origin(payload):
    settings = payload.get('ConfigurationSettings', [])
    if len(settings) != 1:
        raise ValueError('Configuração ausente ou ambígua.')
    options = settings[0].get('OptionSettings', [])
    plain = {i['OptionName']: i.get('Value', '') for i in options
             if i.get('Namespace') == 'aws:elasticbeanstalk:application:environment'}
    secrets = {i['OptionName']: i.get('Value', '') for i in options
               if i.get('Namespace') == 'aws:elasticbeanstalk:application:environmentsecrets'}
    for name in ('SECRET_KEY', 'DATABASE_URL'):
        if not (plain.get(name, '').strip() or secrets.get(name, '').strip()):
            raise ValueError(f'Configuração obrigatória ausente: {name}.')
    if plain.get('DJANGO_SETTINGS_MODULE') != 'config.production' or plain.get('DEBUG', '').lower() != 'false':
        raise ValueError('Settings de produção ou DEBUG incompatível.')
    hosts = [h.strip() for h in plain.get('ALLOWED_HOSTS', '').split(',') if h.strip()]
    origins = [o.strip() for o in plain.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
    if not hosts or any('*' in h or '/' in h or h.startswith('.') for h in hosts):
        raise ValueError('Hosts de produção inválidos.')
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme == 'https' and parsed.hostname in hosts and not parsed.username
                and not parsed.password and not parsed.query and not parsed.fragment
                and parsed.path in ('', '/') and parsed.port in (None, 443)):
            return f'https://{parsed.hostname}'
    raise ValueError('Nenhuma origem HTTPS confiável corresponde aos hosts de produção.')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(origin):
    opener = build_opener(NoRedirect())
    for path in ('/health/', '/readiness/'):
        with opener.open(Request(origin + path, headers={'Accept': 'application/json'}), timeout=10) as response:
            if response.status != 200 or json.loads(response.read(4096)).get('status') != 'ok':
                return False
    return True


def recover(call, execute=False, sleep=time.sleep, clock=time.monotonic, check_http=probe):
    identity = call('sts', 'get-caller-identity')
    expected = f'arn:aws:sts::{ACCOUNT}:assumed-role/MediaTrackGitHubDeployRole/'
    if identity.get('Account') != ACCOUNT or (execute and not identity.get('Arn', '').startswith(expected)):
        raise ValueError('Identidade não autorizada para esta operação.')
    def state():
        return call('elasticbeanstalk', 'describe-environments', '--application-name', APPLICATION,
                    '--environment-names', ENVIRONMENT, '--no-include-deleted')
    before = state()
    current = target(before)
    if current.get('Status') != 'Ready' or current.get('AbortableOperationInProgress'):
        raise ValueError('Ambiente não está pronto ou possui operação concorrente.')
    versions = call('elasticbeanstalk', 'describe-application-versions', '--application-name', APPLICATION,
                    '--version-labels', VERSION).get('ApplicationVersions', [])
    if (len(versions) != 1 or versions[0].get('VersionLabel') != VERSION
            or versions[0].get('SourceBundle') != {'S3Bucket': BUCKET, 'S3Key': KEY}
            or versions[0].get('Status') not in ('UNPROCESSED', 'PROCESSED')):
        raise ValueError('Versão ou origem diferente da aprovada.')
    package = call('s3api', 'head-object', '--bucket', BUCKET, '--key', KEY)
    if package.get('ContentLength') != 98945 or package.get('ETag') != ETAG:
        raise ValueError('Pacote ausente ou alterado desde a aprovação.')
    origin = production_origin(call('elasticbeanstalk', 'describe-configuration-settings',
                                    '--application-name', APPLICATION, '--environment-name', ENVIRONMENT))
    summary = {'version': VERSION, 'environment': ENVIRONMENT, 'region': REGION,
               'previous_version': current.get('VersionLabel'), 'preflight': 'passed'}
    if not execute:
        return summary
    runner = Path(os.environ['RUNNER_TEMP'])
    # Somente campos de estado necessários, nunca a resposta completa.
    fields = ('ApplicationName', 'EnvironmentName', 'EnvironmentId', 'Status', 'Health',
              'VersionLabel', 'AbortableOperationInProgress')
    (runner / 'eb-before.json').write_text(json.dumps({'Environments': [
        {k: current[k] for k in fields if k in current}]}), encoding='utf-8')
    started = datetime.now(timezone.utc).isoformat()
    deadline = clock() + 1800
    call('elasticbeanstalk', 'update-environment', '--environment-name', ENVIRONMENT,
         '--version-label', VERSION)
    consecutive = 0
    while clock() < deadline:
        item = target(state())
        events = call('elasticbeanstalk', 'describe-events', '--environment-name', ENVIRONMENT,
                      '--start-time', started).get('Events', [])
        if any(e.get('Severity') in ('ERROR', 'FATAL') for e in events):
            raise ValueError('Evento de falha após solicitação; não repetir automaticamente.')
        healthy = (item.get('Status') == 'Ready' and item.get('Health') == 'Green'
                   and item.get('VersionLabel') == VERSION and not item.get('AbortableOperationInProgress'))
        http_ok = False
        if healthy:
            try:
                http_ok = check_http(origin)
            except Exception:
                http_ok = False  # URLs e respostas HTTP não são impressas.
        consecutive = consecutive + 1 if healthy and http_ok else 0
        if consecutive >= 5:
            return dict(summary, result='success', consecutive_checks=consecutive)
        sleep(60)
    raise ValueError('Prazo de recuperação excedido; verificar estado sem cancelar ou repetir.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--profile', choices=['mediatrack-production'])
    args = parser.parse_args()
    if args.execute and (args.profile or os.environ.get('GITHUB_ACTIONS') != 'true'
                         or os.environ.get('GITHUB_REPOSITORY') != 'lunecarvalho/media-management-system'
                         or os.environ.get('GITHUB_REF') != 'refs/heads/main'
                         or not os.environ.get('RUNNER_TEMP')):
        parser.exit(1, 'Execução permitida somente pelo workflow protegido na main.\n')
    if not args.execute and not args.profile:
        parser.exit(1, 'Consulta local exige --profile mediatrack-production.\n')
    try:
        summary = recover(lambda *a: aws(*a, profile=args.profile), execute=args.execute)
    except Exception:
        # Nem stderr AWS, nem exceções HTTP/configuração são exibidos.
        parser.exit(1, 'Recuperação/preflight falhou; revisar estados e diagnóstico. Não repetir automaticamente.\n')
    if args.execute:
        (Path(os.environ['RUNNER_TEMP']) / 'eb-recovery.json').write_text(
            json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
