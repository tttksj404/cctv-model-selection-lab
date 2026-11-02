# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false

from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "experiments" / "clip_vitl14_server_bubble_chart.ipynb"


def main() -> None:
    notebook: Any = nbformat.read(NOTEBOOK_PATH, as_version=4)
    client: Any = NotebookClient(notebook, timeout=600, kernel_name="python3")
    client.execute(
        cwd=str(PROJECT_ROOT)
    )
    nbformat.write(notebook, NOTEBOOK_PATH)
    print(f"executed={NOTEBOOK_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
