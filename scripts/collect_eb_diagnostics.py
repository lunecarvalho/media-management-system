"""Coleta somente leitura com campos permitidos; nunca salva respostas AWS brutas."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess


def environment_summary(payload):
    fields = ('ApplicationName', 'EnvironmentName', 'EnvironmentId', 'VersionLabel',
              'Status', 'Health', 'DateUpdated', 'AbortableOperationInProgress')
    return [{key: item[key] for key in fields if key in item}
            for item in payload.get('Environments', [])]


def event_summary(payload):
    # Message pode conter URLs assinadas ou valores de configuração: não preservar.
    fields = ('EventDate', 'Severity', 'RequestId', 'ApplicationName', 'EnvironmentName')
    return [{key: item[key] for key in fields if key in item}
            for item in payload.get('Events', [])]


def query(arguments, region, profile=None):
    command = ['aws', 'elasticbeanstalk', *arguments, '--region', region,
               '--output', 'json', '--no-cli-pager']
    if profile:
        command += ['--profile', profile]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45,
                                check=False)
        if result.returncode:
            return {}, 'aws_query_failed'
        return json.loads(result.stdout), None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}, 'aws_query_unavailable'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('application', 'environment', 'version', 'region', 'output'):
        parser.add_argument(f'--{name}', required=True)
    parser.add_argument('--before', type=Path)
    parser.add_argument('--profile', choices=['mediatrack-production'])
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    report = {'collected_at': now.isoformat(), 'expected_version': args.version,
              'region': args.region, 'errors': []}
    if args.before:
        try:
            report['before'] = environment_summary(json.loads(args.before.read_text()))
        except (OSError, ValueError):
            report['errors'].append('before_unavailable')
    state, error = query(['describe-environments', '--application-name', args.application,
                          '--environment-names', args.environment, '--no-include-deleted'],
                         args.region, args.profile)
    report['after'] = environment_summary(state)
    if error:
        report['errors'].append(f'environment:{error}')
    events, error = query(['describe-events', '--application-name', args.application,
                           '--environment-name', args.environment, '--start-time',
                           (now - timedelta(hours=1)).isoformat(), '--end-time', now.isoformat()],
                          args.region, args.profile)
    report['events'] = event_summary(events)
    if error:
        report['errors'].append(f'events:{error}')
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
