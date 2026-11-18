import shutil
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1] / "API"


@pytest.fixture(scope="session")
def api(tmp_path_factory):
    """A TestClient running on a throwaway copy of the API folder, so retraining never touches the real files."""
    copy = tmp_path_factory.mktemp("api")
    for name in ["prediction.py", "schemas.py", "model_manager.py", "best_model.pkl", "sample_new_loans.csv"]:
        shutil.copy(API / name, copy / name)
    shutil.copytree(API / "data", copy / "data")
    sys.path.insert(0, str(copy))
    from fastapi.testclient import TestClient
    import prediction

    return TestClient(prediction.app), copy
