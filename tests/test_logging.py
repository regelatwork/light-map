import logging
from light_map.display_utils import setup_logging


def test_setup_logging_creates_file(tmp_path):
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=str(log_file))

    logging.info("test message")

    assert log_file.exists()
    with open(log_file, "r") as f:
        content = f.read()
        assert "test message" in content
        assert "INFO" in content


def test_setup_logging_levels(tmp_path):
    log_file = tmp_path / "test_levels.log"
    setup_logging(level=logging.WARNING, log_file=str(log_file))

    logging.info("should not appear")
    logging.warning("should appear")

    with open(log_file, "r") as f:
        content = f.read()
        assert "should not appear" not in content
        assert "should appear" in content


def test_setup_logging_rotation(tmp_path):
    # This is a bit harder to test without mocking RotatingFileHandler
    # but we can try to force a rotation if we set maxBytes very small
    pass
