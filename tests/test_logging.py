import logging

from chat_client.core.logging import NOISY_DEPENDENCY_LOGGERS, setup_logging


def test_setup_logging_raises_noisy_dependency_loggers_to_warning(tmp_path):
    setup_logging(logging.INFO, data_dir=tmp_path)

    for logger_name in NOISY_DEPENDENCY_LOGGERS:
        assert logging.getLogger(logger_name).level == logging.WARNING


def test_setup_logging_preserves_higher_application_log_level_for_dependencies(tmp_path):
    setup_logging(logging.ERROR, data_dir=tmp_path)

    for logger_name in NOISY_DEPENDENCY_LOGGERS:
        assert logging.getLogger(logger_name).level == logging.ERROR
