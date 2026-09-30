from motor_dashboard.normalize import normalize
from motor_dashboard.tests.test_pipeline import row
from motor_dashboard.mock_source import MockSource


def test_signed_base_position_is_forwarded_without_inventing_a_missing_origin():
    manifest = {"runId": "shaft", "motorModel": "XM430-W210", "motorId": 1}
    sample = normalize(row(**{"Base Position": "-1024"}), manifest, {}, 1, "s", "r")
    assert sample["basePosition"] == -1024
    assert normalize(row(), manifest, {}, 2, "s", "r")["basePosition"] is None


def test_mock_reports_its_real_simulation_origin():
    sample = MockSource().sample(0)
    assert sample["basePosition"] == sample["registers"]["132"]["raw"] == 100
