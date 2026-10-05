"""Execute a DuckDB SQL file from the project root.

Uses the duckdb Python package when installed (pip install -r requirements.txt);
otherwise falls back to the DuckDB command-line binary given by $DUCKDB_CLI or found
on PATH. Both run the identical SQL text against wdp.duckdb.

Usage: python scripts/run_sql.py sql/01_load_audit.sql --scope pilot|panel
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'wdp.duckdb'
SCOPES = {
    'panel': {'{{SFX}}': '', '{{PSFX}}': '_panel', '{{WSFX}}': '_panel'},
    'pilot': {'{{SFX}}': '_pilot', '{{PSFX}}': '_pilot', '{{WSFX}}': '_pilot'},
}


def render(sql_path: Path, scope: str) -> str:
    text = sql_path.read_text(encoding='utf-8')
    for k, v in SCOPES[scope].items():
        text = text.replace(k, v)
    return text


def execute(sql: str) -> str:
    os.chdir(ROOT)
    try:
        import duckdb  # type: ignore
        con = duckdb.connect(str(DB))
        con.execute(sql)
        con.close()
        return f'duckdb-python {duckdb.__version__}'
    except ImportError:
        cli = os.environ.get('DUCKDB_CLI') or shutil.which('duckdb')
        if not cli:
            sys.exit('DuckDB not available: pip install duckdb, or set DUCKDB_CLI to the duckdb binary.')
        res = subprocess.run([cli, str(DB)], input=sql, text=True, capture_output=True)
        if res.returncode != 0 or 'Error' in res.stderr:
            sys.exit(f'DuckDB CLI failed:\n{res.stderr[-2000:]}')
        ver = subprocess.run([cli, '--version'], text=True, capture_output=True).stdout.strip()
        return f'duckdb-cli {ver}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sql')
    ap.add_argument('--scope', choices=list(SCOPES), default='panel')
    a = ap.parse_args()
    for d in ['results/checkpoint1', 'data/derived', 'results/analytics', 'results/dashboard']:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    engine = execute(render(ROOT / a.sql, a.scope))
    print(f'ran {a.sql} scope={a.scope} engine={engine}')


if __name__ == '__main__':
    main()
