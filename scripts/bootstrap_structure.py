"""Create all required __init__.py stubs and directories."""
import pathlib

base = pathlib.Path(r'C:/Users/Abhigyan Sharma/OneDrive/Desktop/Autonomous Platform/autonomous-engineering-intelligence')

tool_pkgs = ['code', 'database', 'filesystem', 'git', 'logs', 'metrics', 'retrieval', 'tests']
for pkg in tool_pkgs:
    p = base / 'backend' / 'app' / 'tools' / pkg / '__init__.py'
    if not p.exists():
        p.write_text(f'"""app.tools.{pkg} package"""\n')

for path_parts, content in [
    (['backend', 'app', 'api', 'routes', '__init__.py'], '"""API routes package"""\n'),
    (['backend', 'app', 'api', '__init__.py'], '"""API package"""\n'),
    (['backend', 'app', 'db', '__init__.py'], '"""Database package"""\n'),
    (['backend', 'app', 'core', '__init__.py'], '"""Core package"""\n'),
    (['backend', 'app', '__init__.py'], '"""AEIP Backend application package"""\n'),
]:
    p = base.joinpath(*path_parts)
    if not p.exists():
        p.write_text(content)

for d in ['scripts', 'frontend', 'backend/tests', 'backend/alembic/versions']:
    (base / d).mkdir(parents=True, exist_ok=True)

tests_init = base / 'backend' / 'tests' / '__init__.py'
if not tests_init.exists():
    tests_init.write_text('')

alembic_init = base / 'backend' / 'alembic' / '__init__.py'
if not alembic_init.exists():
    alembic_init.write_text('')

print('Done.')
