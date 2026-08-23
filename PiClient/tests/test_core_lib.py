"""Unit tests for :mod:`piclient.core.lib` (config, controller, exporter, transition manager).

These tests operate on fresh :class:`Config` instances wherever mutation or
freezing is involved so that they never pollute the process-wide
``GLOBAL_CONFIG`` singleton (and so that ordering between test modules does not
matter).
"""

import os
import sys
import types
import unittest
from typing import Literal

import numpy as np
from multiprocessing import shared_memory

from piclient.core.lib import (
    Config,
    Freezeable,
    GLOBAL_CONFIG,
    ProcessContextManager,
    PD,
    TransitionManager,
    export,
    export_globals,
)

class TestFreezeable(unittest.TestCase):
    def test_freeze_blocks_mutation(self):
        class _F(Freezeable):
            def __init__(self):
                self.value = 0

        f = _F()
        f.value = 1  # mutable before freeze
        self.assertEqual(f.value, 1)
        f.freeze()
        with self.assertRaises(AttributeError):
            f.value = 2

    def test_freeze_is_recursive(self):
        parent = Freezeable()
        child = Freezeable()
        parent.child = child
        parent.freeze()
        # Freezing the parent must freeze nested Freezeable attributes too.
        with self.assertRaises(AttributeError):
            child.some_attr = 1


class TestGlobalConfig(unittest.TestCase):
    def test_global_config_singleton(self):
        self.assertIs(GLOBAL_CONFIG(), GLOBAL_CONFIG())

    def test_global_config_returns_config(self):
        self.assertIsInstance(GLOBAL_CONFIG(), Config)

    def test_defaults_present(self):
        cfg = Config()
        self.assertEqual(cfg.CameraConfig.OUTPUT_WIDTH, 512)
        self.assertEqual(cfg.OpenChallengeConfig.WALL_FOLLOW_KPKD, (0.7, 0.5))
        self.assertEqual(cfg.GeneralConfig.CHALLENGE, "open")

    def test_parallel_parking_config_present(self):
        cfg = GLOBAL_CONFIG()
        self.assertTrue(hasattr(cfg, "ParallelParkingConfig"))
        self.assertTrue(cfg.ParallelParkingConfig.WALL_FOLLOW_TARGET_DISTANCE)
        self.assertTrue(cfg.ParallelParkingConfig.ARC_ONE_SERVO_ANGLE)


class TestConfigMutability(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_scalar_mutability(self):
        self.config.GeneralConfig.LEVEL = "DEBUG"
        self.assertEqual(self.config.GeneralConfig.LEVEL, "DEBUG")
        self.config.GeneralConfig.LEVEL = "INFO"
        self.assertEqual(self.config.GeneralConfig.LEVEL, "INFO")

    def test_tuple_mutability(self):
        self.config.VisionConfig.LOWER_BLACK = (1, 2, 3)
        self.assertEqual(self.config.VisionConfig.LOWER_BLACK, (1, 2, 3))
        self.config.VisionConfig.LOWER_BLACK = (4, 5, 6)
        self.assertEqual(self.config.VisionConfig.LOWER_BLACK, (4, 5, 6))

    def test_freeze_blocks_nested_mutation(self):
        self.config.freeze()
        with self.assertRaises(AttributeError):
            self.config.GeneralConfig.LEVEL = "ERROR"

    def test_repr_lists_sections(self):
        text = repr(self.config)
        self.assertIn("GeneralConfig", text)
        self.assertIn("VisionConfig", text)


class TestConfigNestedAccess(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_get_nested_attr(self):
        value = self.config._get_nested_attr("GeneralConfig.LEVEL") # pyright: ignore[reportPrivateUsage]
        self.assertEqual(value, self.config.GeneralConfig.LEVEL)

    def test_set_nested_attr(self):
        self.config.set_nested_attr("GeneralConfig.LEVEL", "DEBUG")
        self.assertEqual(self.config.GeneralConfig.LEVEL, "DEBUG")

    def test_set_nested_attr_ignores_missing_leaf(self):
        # Setting a non-existent leaf is a silent no-op (hasattr guard).
        self.config.set_nested_attr("GeneralConfig.DOES_NOT_EXIST", "x")
        self.assertFalse(hasattr(self.config.GeneralConfig, "DOES_NOT_EXIST"))

    def test_get_annotation(self):
        annotation = self.config.get_annotation("VisionConfig.LOWER_BLACK")
        self.assertEqual(annotation, tuple[int, int, int])

    def test_get_annotation_missing_raises(self):
        with self.assertRaises(TypeError):
            self.config.get_annotation("GeneralConfig._frozen")


class TestConfigCasters(unittest.TestCase):
    def test_primitive_casters(self):
        self.assertEqual(Config.get_caster(int)("5"), 5)
        self.assertEqual(Config.get_caster(float)("2.5"), 2.5)
        self.assertEqual(Config.get_caster(str)("hi"), "hi")

    def test_bool_caster(self):
        bool_caster = Config.get_caster(bool)
        self.assertTrue(bool_caster("true"))
        self.assertTrue(bool_caster("1"))
        self.assertTrue(bool_caster("yes"))
        self.assertFalse(bool_caster("false"))
        self.assertFalse(bool_caster("0"))

    def test_tuple_caster(self):
        self.assertEqual(Config.get_caster(tuple)("(1, 2, 3)"), (1, 2, 3))

    def test_caster_by_origin(self):
        # tuple[int, int, int] should resolve via its origin (tuple).
        caster = Config.get_caster(tuple[int, int, int])
        self.assertEqual(caster("(7, 8, 9)"), (7, 8, 9))

    def test_ndarray_caster(self):
        annotation = Config().get_annotation("VisionConfig.PERSPECTIVE_TRANSFORM")
        # will raise if not equal
        np.testing.assert_array_equal(Config.get_caster(annotation)("[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]"), np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32))

    def test_missing_caster_raises(self):
        with self.assertRaises(TypeError):
            Config.get_caster(complex)


class TestConfigFromToml(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        os.makedirs("./test_data", exist_ok=True)
        self.path = "./test_data/lib_config.toml"

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.isdir("./test_data") and not os.listdir("./test_data"):
            os.rmdir("./test_data")

    def _write(self, content: str):
        with open(self.path, "w") as f:
            f.write(content)

    def test_from_toml_hydrates_sections(self):
        self._write(
            "[GeneralConfig]\nLEVEL = \"ERROR\"\n\n"
            "[VisionConfig]\nLOWER_BLACK = [10, 10, 10]\nUPPER_BLACK = [20, 20, 20]\n"
        )
        cfg = self.config.from_toml(self.path)
        self.assertIs(cfg, self.config)
        self.assertEqual(cfg.GeneralConfig.LEVEL, "ERROR")
        self.assertEqual(list(cfg.VisionConfig.LOWER_BLACK), [10, 10, 10])
        self.assertEqual(list(cfg.VisionConfig.UPPER_BLACK), [20, 20, 20])

    def test_from_toml_missing_file(self):
        with self.assertRaises(OSError):
            self.config.from_toml("./test_data/nope.toml")

    def test_from_toml_unknown_section(self):
        self._write("[NotAConfig]\nX = 1\n")
        with self.assertRaises(AttributeError):
            self.config.from_toml(self.path)

    def test_from_toml_section_not_table(self):
        self._write("GeneralConfig = 5\n")
        with self.assertRaises(AttributeError):
            self.config.from_toml(self.path)

    def test_from_toml_bad_field(self):
        self._write("[GeneralConfig]\nNONEXISTENT_FIELD = 1\n")
        with self.assertRaises(AttributeError):
            self.config.from_toml(self.path)


class TestConfigFromEnv(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        # Remove any WRO_ variables leaked by other test modules so the
        # environment is deterministic for this test.
        self._saved = {k: v for k, v in os.environ.items() if k.startswith("WRO__")}
        for key in self._saved:
            del os.environ[key]

    def tearDown(self):
        for key in [k for k in os.environ if k.startswith("WRO__")]:
            del os.environ[key]
        os.environ.update(self._saved)

    def test_from_env_scalar(self):
        os.environ["WRO__GeneralConfig__LEVEL"] = "DEBUG"
        cfg = self.config.from_env()
        self.assertEqual(cfg.GeneralConfig.LEVEL, "DEBUG")

    def test_from_env_case_insensitive_section(self):
        os.environ["WRO__GENERALCONFIG__LEVEL"] = "INFO"
        cfg = self.config.from_env()
        self.assertEqual(cfg.GeneralConfig.LEVEL, "INFO")

    def test_from_env_tuple(self):
        os.environ["WRO__VisionConfig__LOWER_BLACK"] = "[5, 5, 5]"
        cfg = self.config.from_env()
        self.assertEqual(list(cfg.VisionConfig.LOWER_BLACK), [5, 5, 5])

    def test_from_env_ignores_non_prefixed(self):
        os.environ["NOT_WRO_LEVEL"] = "DEBUG"
        try:
            cfg = self.config.from_env()
            self.assertEqual(cfg.GeneralConfig.LEVEL, Config().GeneralConfig.LEVEL)
        finally:
            del os.environ["NOT_WRO_LEVEL"]


class TestPDController(unittest.TestCase):
    def test_initialization(self):
        controller = PD(1.0, 0.1)
        self.assertEqual(controller.KP, 1.0)
        self.assertEqual(controller.KD, 0.1)
        self.assertEqual(controller.previous_error, 0)

    def test_tick_as_error_signal(self):
        controller = PD(1.0, 0.1)
        # First tick: derivative uses previous_error == 0.
        self.assertAlmostEqual(controller.tick(0.5), 1.0 * 0.5 + 0.1 * 0.5)
        # Second tick: derivative uses previous error 0.5.
        self.assertAlmostEqual(controller.tick(0.2), 1.0 * 0.2 + 0.1 * (0.2 - 0.5))

    def test_tick_with_target(self):
        controller = PD(2.0, 0.0)
        # error = target - value = 10 - 4 = 6
        self.assertAlmostEqual(controller.tick(4.0, target=10.0), 12.0)

    def test_previous_error_updates(self):
        controller = PD(1.0, 1.0)
        controller.tick(3.0)
        self.assertEqual(controller.previous_error, 3.0)


class TestExporter(unittest.TestCase):
    def _make_module(self, name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        return module

    def test_export_creates_all(self):
        module = self._make_module("_fake_export_mod")

        def sample():
            pass

        sample.__module__ = module.__name__
        returned = export(sample)
        self.assertIs(returned, sample)
        self.assertEqual(module.__all__, ["sample"])

    def test_export_appends_and_deduplicates(self):
        module = self._make_module("_fake_export_mod2")

        def one():
            pass

        def two():
            pass

        one.__module__ = two.__module__ = module.__name__
        export(one)
        export(two)
        export(one)  # duplicate must not be re-added
        self.assertEqual(module.__all__, ["one", "two"])

    def test_export_globals_collects_public_names(self):
        module = self._make_module("_fake_export_globals_mod")
        module.__dict__["export_globals"] = export_globals
        exec(
            "public_value = 1\n"
            "_private_value = 2\n"
            "def public_func():\n    pass\n"
            "export_globals()\n",
            module.__dict__,
        )
        self.assertIn("public_value", module.__all__)
        self.assertIn("public_func", module.__all__)
        self.assertNotIn("_private_value", module.__all__)
        self.assertNotIn("export_globals", module.__all__)


class TestTransitionManager(unittest.TestCase):
    def test_validation_hysteresis_length(self):
        with self.assertRaises(ValueError):
            TransitionManager(hysteresis_values=[1, 2], priorities=[0], a=lambda: True)

    def test_validation_priority_length(self):
        with self.assertRaises(ValueError):
            TransitionManager(hysteresis_values=[1], priorities=[0, 1], a=lambda: True)

    def test_validation_unique_priorities(self):
        with self.assertRaises(ValueError):
            TransitionManager(hysteresis_values=[1, 1], priorities=[0, 0], a=lambda: True, b=lambda: True)

    def test_validation_non_negative_priority(self):
        with self.assertRaises(ValueError):
            TransitionManager(hysteresis_values=[1], priorities=[-1], a=lambda: True)

    def test_validation_non_negative_hysteresis(self):
        with self.assertRaises(ValueError):
            TransitionManager(hysteresis_values=[-1], priorities=[0], a=lambda: True)

    def test_hysteresis_threshold(self):
        tm = TransitionManager[[], Literal["a"]](hysteresis_values=[2], priorities=[0], a=lambda: True)
        self.assertIsNone(tm.check_transitions())  # counter 1 < 2
        self.assertEqual(tm.check_transitions(), "a")  # counter 2 >= 2
        # After a transition all counters reset, so it needs to build up again.
        self.assertIsNone(tm.check_transitions())

    def test_zero_hysteresis_fires_immediately(self):
        tm = TransitionManager[[], Literal["a"]](hysteresis_values=[0], priorities=[0], a=lambda: True)
        self.assertEqual(tm.check_transitions(), "a")

    def test_false_determinant_resets_counter(self):
        toggler = {"value": True}
        tm = TransitionManager[[], Literal["a"]](hysteresis_values=[2], priorities=[0], a=lambda: toggler["value"])
        self.assertIsNone(tm.check_transitions())  # counter 1
        toggler["value"] = False
        self.assertIsNone(tm.check_transitions())  # reset to 0
        toggler["value"] = True
        self.assertIsNone(tm.check_transitions())  # counter 1 again, not 2

    def test_priority_wins(self):
        tm = TransitionManager[[], Literal["low", "high"]](
            hysteresis_values=[0, 0],
            priorities=[1, 5],
            low=lambda: True,
            high=lambda: True,
        )
        self.assertEqual(tm.check_transitions(), "high")

    def test_signature_mismatch_is_skipped(self):
        # `needs_arg` binds the positional argument; `no_arg` cannot and is skipped.
        # Look like my typing efforts are paying off! The type checker will catch this at compile time, but we also want to ensure that the runtime behavior is correct.
        def x_needs_arg(x: int):
            return x > 0
        def y_no_arg():
            return True
        
        tm = TransitionManager[
            [], 
            Literal["with_arg", "no_arg"]
        ](
            hysteresis_values=[0, 0],
            priorities=[0, 1],
            with_arg=x_needs_arg, # pyright: ignore[reportArgumentType]
            no_arg=y_no_arg, # pyright: ignore[reportArgumentType]
        )
        # no_arg has higher priority but is skipped because it can't bind (5,).
        self.assertEqual(tm.check_transitions(5), "with_arg") # pyright: ignore[reportCallIssue]

class TestProcessManager(unittest.TestCase):
    def test_process_context_manager_allocates_expected_shared_memory(self):
        def camera_callback(shm_name: str, *senders: object) -> None:
            del shm_name, senders

        def vision_callback(shm_name: str, *pipes: object) -> None:
            del shm_name, pipes

        def recorder_callback(shm_name: str, receiver: object) -> None:
            del shm_name, receiver

        shm_name = "test_process_manager_shm"
        shm_size = 1024

        process_manager = ProcessContextManager(
            camera_callback=camera_callback,
            vision_callback=vision_callback,
            recorder_callback=recorder_callback,
            shm_size=shm_size,
            shm_name=shm_name,
        )

        with process_manager as context:
            # After __enter__ is called, the shared memory should be allocated and accessible.
            shm: shared_memory.SharedMemory = context.shm # pyright: ignore[reportAssignmentType]
            self.assertIsInstance(shm, shared_memory.SharedMemory)
            self.assertEqual(context.shm_size, shm_size)
            self.assertEqual(shm.name, shm_name)
            self.assertIsNotNone(context.output_stream)

        with self.assertRaises(FileNotFoundError):
            shared_memory.SharedMemory(name=shm_name)

if __name__ == "__main__":
    unittest.main()
