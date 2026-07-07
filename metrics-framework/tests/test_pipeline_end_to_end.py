import json
import os

from framework.config import load_config
from framework.pipeline import run_pipeline, write_outputs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG_PATH = os.path.join(FIXTURES, "config.test.yaml")


def test_end_to_end_writes_dashboard_shaped_output(tmp_path):
    config = load_config(CONFIG_PATH)
    result = run_pipeline(CONFIG_PATH)
    write_outputs(result, config, base_dir=str(tmp_path))

    json_path = tmp_path / "out" / "test_metrics.json"
    js_path = tmp_path / "out" / "test_dashboard_data.js"
    assert json_path.exists()
    assert js_path.exists()

    data = json.loads(json_path.read_text())
    for key in ("meta", "LEVELS", "DIMENSIONS", "DIVISIONS"):
        assert key in data
    assert len(data["LEVELS"]) == 4
    assert len(data["DIMENSIONS"]) == 5
    assert len(data["DIVISIONS"]) == 2
    for dim in data["DIMENSIONS"]:
        for required in ("id", "name", "orgLevel", "orgTrend", "orgHi"):
            assert required in dim
        assert 1 <= dim["orgLevel"] <= 4

    js_text = js_path.read_text()
    assert js_text.startswith("window.DASHBOARD_DATA = ")
    # the JS file must be valid JSON once the `window.DASHBOARD_DATA = ` / trailing `;` are stripped
    payload = js_text[len("window.DASHBOARD_DATA = "):].rstrip("\n").rstrip(";")
    reparsed = json.loads(payload)
    assert reparsed == data


def test_one_broken_source_does_not_abort_the_whole_run(tmp_path):
    import shutil
    import yaml

    broken_dir = tmp_path / "broken"
    shutil.copytree(FIXTURES, broken_dir)
    cfg = yaml.safe_load((broken_dir / "config.test.yaml").read_text())
    cfg["sources"][0]["path"] = "does_not_exist.csv"  # break the roster source specifically
    (broken_dir / "config.test.yaml").write_text(yaml.dump(cfg))

    result = run_pipeline(str(broken_dir / "config.test.yaml"))
    assert result["meta"]["sourcesFailed"] == 1
    assert "roster" in result["meta"]["sourceErrors"][0]
    # the other 10 sources should have still run and produced dimension scores
    assert len(result["DIMENSIONS"]) == 5
