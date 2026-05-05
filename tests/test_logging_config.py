from __future__ import annotations

import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from app import logging_config


class LoggingConfigTest(unittest.TestCase):
    def test_configure_logging_writes_all_and_error_files(self) -> None:
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level
        original_log_dir = logging_config.LOG_DIR
        original_all_path = logging_config.APP_LOG_PATH
        original_error_path = logging_config.ERROR_LOG_PATH
        original_stderr = sys.stderr
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                base_dir = Path(tmp_dir)
                logging_config.LOG_DIR = base_dir
                logging_config.APP_LOG_PATH = base_dir / "all.log"
                logging_config.ERROR_LOG_PATH = base_dir / "errors.log"

                sys.stderr = io.StringIO()
                logging_config.configure_logging()
                test_logger = logging.getLogger("tests.logging_config")
                test_logger.info("info marker")
                test_logger.error("error marker")
                for handler in root_logger.handlers:
                    handler.flush()

                all_log = logging_config.APP_LOG_PATH.read_text(encoding="utf-8")
                error_log = logging_config.ERROR_LOG_PATH.read_text(encoding="utf-8")
                self.assertIn("info marker", all_log)
                self.assertIn("error marker", all_log)
                self.assertNotIn("info marker", error_log)
                self.assertIn("error marker", error_log)
        finally:
            for handler in root_logger.handlers:
                handler.close()
            root_logger.handlers.clear()
            for handler in original_handlers:
                root_logger.addHandler(handler)
            root_logger.setLevel(original_level)
            logging_config.LOG_DIR = original_log_dir
            logging_config.APP_LOG_PATH = original_all_path
            logging_config.ERROR_LOG_PATH = original_error_path
            sys.stderr = original_stderr

    def test_export_log_file_copies_selected_log(self) -> None:
        original_all_path = logging_config.APP_LOG_PATH
        original_error_path = logging_config.ERROR_LOG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                base_dir = Path(tmp_dir)
                source = base_dir / "source.log"
                destination = base_dir / "exports" / "saved.log"
                source.write_text("hello\n", encoding="utf-8")
                logging_config.APP_LOG_PATH = source
                logging_config.ERROR_LOG_PATH = base_dir / "errors.log"

                exported = logging_config.export_log_file("all", destination)

                self.assertEqual(exported, destination)
                self.assertEqual(destination.read_text(encoding="utf-8"), "hello\n")
        finally:
            logging_config.APP_LOG_PATH = original_all_path
            logging_config.ERROR_LOG_PATH = original_error_path

    def test_log_file_path_rejects_unknown_kind(self) -> None:
        with self.assertRaises(ValueError):
            logging_config.log_file_path("debug")


if __name__ == "__main__":
    unittest.main()
