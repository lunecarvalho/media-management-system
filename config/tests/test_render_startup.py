import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase


class RenderStartupTests(SimpleTestCase):
    def test_bootstrap_handoff_clears_credentials_and_stops_on_error(self):
        shell = shutil.which('sh')
        if not shell and os.name == 'nt':
            candidate = Path('C:/Program Files/Git/bin/sh.exe')
            if candidate.exists():
                shell = str(candidate)
        if not shell:
            self.skipTest('POSIX shell unavailable')
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='mediatrack-bootstrap-') as directory:
            folder = Path(directory)
            (folder / 'scripts').mkdir()
            script = folder / 'scripts/bootstrap-render-admin.sh'
            script.write_bytes((root / 'scripts/bootstrap-render-admin.sh').read_bytes())
            self.assertNotIn(b'\r', script.read_bytes())
            (folder / 'scripts/start-render.sh').write_text(
                '#!/bin/sh\n'
                '[ "${DJANGO_SUPERUSER_USERNAME+set}" != set ] || exit 31\n'
                '[ "${DJANGO_SUPERUSER_EMAIL+set}" != set ] || exit 32\n'
                '[ "${DJANGO_SUPERUSER_PASSWORD+set}" != set ] || exit 33\n'
                '[ "$DJANGO_SETTINGS_MODULE" = config.render ] || exit 34\n'
                'printf "normal startup\\n"\n', encoding='utf-8', newline='\n',
            )
            stub = folder / 'python'
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*"\nexit "$BOOTSTRAP_EXIT"\n',
                            encoding='utf-8', newline='\n')
            subprocess.run([shell, '-c', 'chmod +x "$1"', 'test', stub.as_posix()], check=True)
            for code in ('0', '17'):
                env = dict(os.environ, BOOTSTRAP_EXIT=code, DJANGO_SETTINGS_MODULE='config.render',
                           DJANGO_SUPERUSER_USERNAME='fake-admin',
                           DJANGO_SUPERUSER_EMAIL='fake@example.invalid',
                           DJANGO_SUPERUSER_PASSWORD='fake-secret')
                result = subprocess.run(
                    [shell, '-c', 'PATH="$(cd "$1" && pwd):$PATH"; export PATH; exec sh "$2"',
                     'test', folder.as_posix(), script.as_posix()],
                    env=env, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, int(code), result.stderr)
                self.assertEqual(result.stdout.splitlines(),
                                 ['manage.py bootstrap_render_admin'] +
                                 (['normal startup'] if code == '0' else []))
                self.assertNotIn('fake-secret', result.stdout + result.stderr)

    def test_migration_order_port_and_failure_without_database(self):
        shell = shutil.which('sh')
        if not shell and os.name == 'nt':
            candidate = Path('C:/Program Files/Git/bin/sh.exe')
            if candidate.exists():
                shell = str(candidate)
        if not shell:
            self.skipTest('POSIX shell unavailable')
        script = Path(__file__).resolve().parents[2] / 'scripts/start-render.sh'
        self.assertNotIn(b'\r', script.read_bytes())
        syntax = subprocess.run([shell, '-n', str(script)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        with tempfile.TemporaryDirectory(prefix='mediatrack-startup-') as directory:
            folder = Path(directory)
            for name, body in {
                'python': 'printf "migration:%s\\n" "$*"\nexit "${MIGRATION_EXIT:-0}"\n',
                'gunicorn': 'printf "server:%s\\n" "$*"\n',
            }.items():
                stub = folder / name
                stub.write_text('#!/bin/sh\n' + body, encoding='utf-8', newline='\n')
                subprocess.run([shell, '-c', 'chmod +x "$1"', 'test', stub.as_posix()], check=True)
            for port, migration_exit in (('', '0'), ('12345', '0'), ('12345', '17')):
                with self.subTest(port=port, migration_exit=migration_exit):
                    env = dict(os.environ, PORT=port, MIGRATION_EXIT=migration_exit)
                    result = subprocess.run(
                        [shell, '-c', 'PATH="$(cd "$1" && pwd):$PATH"; export PATH; exec sh "$2"',
                         'test', folder.as_posix(), script.as_posix()],
                        env=env, capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(result.returncode, int(migration_exit), result.stderr)
                    lines = result.stdout.splitlines()
                    self.assertEqual(lines[0], 'migration:manage.py migrate --noinput')
                    if migration_exit == '0':
                        self.assertEqual(len(lines), 2)
                        self.assertIn(f'--bind 0.0.0.0:{port or "10000"}', lines[1])
                        self.assertIn('--workers 2 --timeout 45 --access-logfile - --error-logfile -', lines[1])
                    else:
                        self.assertEqual(len(lines), 1)
