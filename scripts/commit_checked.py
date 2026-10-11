"""Commit condizionato all'esito dei test (02-convenzioni.md §8, punto 9).

Uso: ``git add …`` poi ``uv run python scripts/commit_checked.py -m "messaggio"``.

1. Esegue i test di default: se uno fallisce, nessun commit (uscita 1).
2. Esegue a parte i test di rete (marcatore ``network``, ripetuti come da punto 8):
   - tutti passano → commit con il messaggio dato;
   - falliscono solo per connessione (proprietà ``network_final``) → commit, con il
     messaggio che lo dichiara (test e motivo);
   - un test di rete fallisce per un altro motivo → nessun commit (uscita 1).
   Con ``--no-network`` i test di rete non si eseguono (parti intermedie di un modulo,
   eseguiti alla fine del modulo) e il messaggio di commit lo dichiara.
"""

import argparse
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_pytest(*args: str, junit: Path | None = None) -> int:
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args]
    if junit is not None:
        command.append(f"--junitxml={junit}")
    return subprocess.run(command, cwd=ROOT).returncode


def network_failures(junit: Path) -> tuple[list[str], list[str]]:
    """(falliti solo per connessione, falliti per altri motivi) dal rapporto JUnit."""
    by_connection, other = [], []
    for case in ET.parse(junit).getroot().iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        name = f"{case.get('classname')}::{case.get('name')}"
        reasons = [p.get("value") for p in case.iter("property") if p.get("name") == "network_final"]
        (by_connection if reasons else other).append(f"{name} ({reasons[0]})" if reasons else name)
    return by_connection, other


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-m", "--message", required=True, help="messaggio di commit")
    parser.add_argument("--no-network", action="store_true",
                        help="non eseguire i test di rete (dichiarato nel messaggio di commit)")
    args = parser.parse_args()

    if run_pytest() != 0:
        print("Test di default falliti: nessun commit.", file=sys.stderr)
        return 1

    if args.no_network:
        message = args.message + ("\n\nTest di rete non eseguiti in questo commit: si eseguono "
                                  "alla fine del modulo (02-convenzioni.md §8, punto 9).")
        return subprocess.run(["git", "commit", "-m", message], cwd=ROOT).returncode

    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "network.xml"
        code = run_pytest("-m", "network", junit=junit)
        if code not in (0, 1, 5):  # 5 = nessun test di rete raccolto
            print(f"Esecuzione dei test di rete interrotta (codice {code}): nessun commit.", file=sys.stderr)
            return 1
        by_connection, other = network_failures(junit) if junit.exists() else ([], [])

    if other:
        print("Test di rete falliti per un motivo diverso dalla connessione: nessun commit.\n  "
              + "\n  ".join(other), file=sys.stderr)
        return 1

    message = args.message
    if by_connection:
        message += ("\n\nTest di rete falliti solo per connessione dopo le ripetizioni "
                    "(02-convenzioni.md §8, punto 9):\n" + "\n".join(f"- {t}" for t in by_connection))
    return subprocess.run(["git", "commit", "-m", message], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
