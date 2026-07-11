import unittest
import os
import numpy as np
from piclient.cli import TypedArgumentParser
from piclient.core.lib import GLOBAL_CONFIG, Config


class TestTypedArgumentParser(unittest.TestCase):
    def setUp(self):
        self.parser = TypedArgumentParser(GLOBAL_CONFIG())

    def test_parse_args_with_valid_input(self):
        args = ['--GeneralConfig.LEVEL', 'DEBUG']
        self.parser.parse_args(args)
        self.assertEqual(GLOBAL_CONFIG().GeneralConfig.LEVEL, 'DEBUG')

    def test_parse_args_with_invalid_input(self):
        # Note: Enforcing Literals is not possible with the current implementation.
        # This test will pass, but in a real-world scenario, you would want to validate the input against the allowed values.
        args = ['--GeneralConfig.NONEXISTENT', '']
        with self.assertRaises(SystemExit):
            self.parser.parse_args(args)

    def test_parse_args_with_no_input(self):
        GLOBAL_CONFIG().GeneralConfig.LEVEL = 'WARNING'  # Reset to default
        args = []
        self.parser.parse_args(args)
        self.assertEqual(GLOBAL_CONFIG().GeneralConfig.LEVEL,
                         'WARNING')  # Code defaults

    # Hard tests
    def test_parse_args_with_complex_data_types(self):
        args = ['--VisionConfig.PERSPECTIVE_TRANSFORM',
                '[[1, 2, 3],[4, 5, 6],[7, 8, 9]]']
        self.parser.parse_args(args)
        self.assertIsInstance(
            GLOBAL_CONFIG().VisionConfig.PERSPECTIVE_TRANSFORM, np.ndarray)
        self.assertEqual(GLOBAL_CONFIG().VisionConfig.PERSPECTIVE_TRANSFORM.tolist(), [
                         [1, 2, 3], [4, 5, 6], [7, 8, 9]])

    def test_parse_args_with_multiple_values(self):
        args = ['--GeneralConfig.LEVEL', 'INFO',
                '--VisionConfig.LOWER_BLACK', '[0, 0, 0]']
        self.parser.parse_args(args)
        self.assertEqual(GLOBAL_CONFIG().GeneralConfig.LEVEL, 'INFO')
        self.assertEqual(GLOBAL_CONFIG().VisionConfig.LOWER_BLACK, [0, 0, 0])

    def test_parse_args_with_mixed_env_toml_and_cli(self):
        # Simulate environment variable
        os.environ['WRO__GenERalCONfIG__LEVEL'] = 'INFO'
        os.environ['WRO__VisionConfig__LOWER_BLACK'] = '[5, 5, 5]'

        # Simulate TOML file
        def fake_from_toml(path: str = "./test_data/test_config.toml") -> Config:
            GLOBAL_CONFIG().GeneralConfig.LEVEL = 'ERROR'
            GLOBAL_CONFIG().VisionConfig.LOWER_BLACK = (10, 10, 10)
            GLOBAL_CONFIG().VisionConfig.UPPER_BLACK = (20, 20, 20)
            return GLOBAL_CONFIG()

        GLOBAL_CONFIG().from_toml = fake_from_toml

        args = ['--GeneralConfig.LEVEL', 'DEBUG']

        GLOBAL_CONFIG().from_toml()
        GLOBAL_CONFIG().from_env()
        self.parser.parse_args(args)

        # CLI args should take precedence over env and toml
        self.assertEqual(GLOBAL_CONFIG().GeneralConfig.LEVEL, 'DEBUG')
        # Environment variable should take precedence over TOML
        self.assertEqual(
            list(GLOBAL_CONFIG().VisionConfig.LOWER_BLACK), [5, 5, 5])
        self.assertEqual(list(
            GLOBAL_CONFIG().VisionConfig.UPPER_BLACK), [20, 20, 20])
        

class TestTOMLFileLoading(unittest.TestCase):
    def setUp(self):
        os.makedirs("./test_data", exist_ok=True)

    def test_toml_loading(self):
        with open("./test_data/test_config.toml", "x") as f:
            f.write("""
                [GeneralConfig]
                LEVEL = "ERROR"

                [VisionConfig]
                LOWER_BLACK = [10, 10, 10]
                UPPER_BLACK = [20, 20, 20]
            """)

        config = GLOBAL_CONFIG().from_toml("./test_data/test_config.toml")

        self.assertEqual(config.GeneralConfig.LEVEL, 'ERROR')
        self.assertEqual(list(config.VisionConfig.LOWER_BLACK), [10, 10, 10])
        self.assertEqual(list(config.VisionConfig.UPPER_BLACK), [20, 20, 20])

    def test_toml_loading_with_invalid_file(self):
        with self.assertRaises(OSError):
            GLOBAL_CONFIG().from_toml("./test_data/non_existent_config.toml")

    def test_toml_loading_with_invalid_content(self):
        with open("./test_data/invalid_config.toml", "x") as f:
            f.write("INVALID TOML CONTENT")

        with self.assertRaises(Exception):
            GLOBAL_CONFIG().from_toml("./test_data/invalid_config.toml")

    def tearDown(self):
        if os.path.exists("./test_data/test_config.toml"):
            os.remove("./test_data/test_config.toml")
        if os.path.exists("./test_data/invalid_config.toml"):
            os.remove("./test_data/invalid_config.toml")
        if os.path.exists("./test_data"):
            os.rmdir("./test_data")
