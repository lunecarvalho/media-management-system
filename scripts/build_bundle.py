"""Pacote Elastic Beanstalk determinístico e restrito a código/estáticos."""
import argparse
import ssl
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('acervo', 'api', 'categorias', 'config', 'integracoes', 'movimentacoes', 'usuarios', 'templates', 'static')
FILES = ('Dockerfile', 'requirements.txt', '.python-version', 'manage.py', '.dockerignore')
EXTENSIONS = {'.py', '.html', '.css', '.js', '.svg', '.png', '.jpg', '.ico', '.woff', '.woff2'}
EXCLUDED = {'__pycache__', 'tests', '.git', '.env', '.aws', 'datasets', 'backups'}


def add(archive, name, content):
    info = ZipInfo(str(name).replace('\\', '/'), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def bundle(destination, rds_ca=None):
    ca = None
    if rds_ca:
        path = Path(rds_ca)
        ca = path.read_bytes()
        if len(ca) > 2 * 1024 * 1024 or b'PRIVATE KEY' in ca:
            raise ValueError('Informe somente o bundle público de CA, sem chave privada.')
        ssl.create_default_context(cafile=str(path))  # Confirma que é um PEM válido.
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if path.is_symlink():
                raise ValueError('Arquivo de build não pode ser um link simbólico.')
            add(archive, name, path.read_bytes())
        for name in DIRECTORIES:
            for path in sorted((ROOT / name).rglob('*')):
                relative = path.relative_to(ROOT)
                if (path.is_file() and not path.is_symlink() and ROOT.resolve() in path.resolve().parents
                        and not EXCLUDED.intersection(relative.parts)
                        and not any(part.startswith('.') for part in relative.parts)
                        and path.suffix in EXTENSIONS):
                    add(archive, relative, path.read_bytes())
        if ca:
            add(archive, 'certs/rds-ca.pem', ca)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rds-ca', help='Caminho local do certificado público RDS; nunca uma chave.')
    parser.add_argument('--output', default=str(ROOT / 'dist' / 'mediatrack.zip'))
    args = parser.parse_args()
    print(bundle(args.output, args.rds_ca))
