"""
Process context manager for the PiClient.
This module provides ``ProcessContextManager`` for managing the lifecycle of the piclient application.
The process archetecture is currently fixed, but will be updated in the future
to support downstream use cases.
"""

from typing import Any, NoReturn, TypeVar, overload

from collections.abc import Callable
import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import Connection

from loguru import logger
from piclient.core.lib import GLOBAL_CONFIG, export

_S = TypeVar('_S', bound=str)  # TypeVar for shared memory name


@export
class ProcessContextManager:
    _DEFAULT_SHM_SIZE: int = GLOBAL_CONFIG().CameraConfig.SHM_SIZE
    _DEFAULT_SHM_NAME: str = GLOBAL_CONFIG().SharedChallengeConfig.SHM_NAME
    _STUB_RECORDER_CALLBACK = None

    @overload
    def __init__(
        self,
        camera_callback: Callable[[_S, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[_S, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[_S, "Connection[Any, Any]"], NoReturn | None] | None = None,
        shm_size: int | None = None,
        shm_name: _S = ...
    ) -> None: ...

    @overload
    def __init__(
        self,
        camera_callback: Callable[[str, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[str, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[str, "Connection[Any, Any]"], NoReturn] | None = None,
        shm_size: int | None = None,
        shm_name: None = None
    ) -> None: ...

    def __init__(
        self,
        camera_callback: Callable[[Any, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[Any, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[Any, "Connection[Any, Any]"], NoReturn | None] | None = None,
        shm_size: int | None = None,
        shm_name: Any = None
    ):
        """Initialize the process context manager.

        :param shm_size: Size of the shared memory segment. If None, uses the default size.
        :param shm_name: Name of the shared memory segment. If None, uses the default name.
        :param camera_callback: The callback function to be called in the camera process.
        :param vision_callback: The callback function to be called in the vision process.
        :param recorder_callback: The callback function to be called in the recorder process.
        """
        self.shm_size = shm_size if shm_size is not None else self._DEFAULT_SHM_SIZE
        self.shm_name = shm_name if shm_name is not None else self._DEFAULT_SHM_NAME
        self.camera_callback = camera_callback
        self.vision_callback = vision_callback
        self.recorder_callback = recorder_callback if recorder_callback is not None else self._STUB_RECORDER_CALLBACK

        self.shm = None
        self.camera_process = None
        self.vision_process = None
        self.output_stream = None

    def __enter__(self):
        """Enter the process context manager."""
        try:
            self.shm = shared_memory.SharedMemory(
                create=True, size=self.shm_size, name=self.shm_name)
        except FileExistsError:
            try:
                self.shm = shared_memory.SharedMemory(name=self.shm_name)
                self.shm.close()
                self.shm.unlink()
                # Make sure it has exactly the size we need, and is empty
                self.shm = shared_memory.SharedMemory(
                    create=True, size=self.shm_size, name=self.shm_name)
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                self.shm = shared_memory.SharedMemory(
                    create=True, size=self.shm_size, name=self.shm_name)

        vision_receiver, vision_sender = mp.Pipe(duplex=False)
        recorder_receiver, recorder_sender = mp.Pipe(duplex=False)
        self.camera_process = mp.Process(
            name="Camera",
            target=self.camera_callback,
            args=(self.shm.name, vision_sender, recorder_sender)
        )
        self.camera_process.start()

        data_receiver, data_sender = mp.Pipe(duplex=False)
        self.vision_process = mp.Process(
            name="Vision",
            target=self.vision_callback,
            args=(
                self.shm.name,
                vision_receiver,
                data_sender,
            )
        )
        self.vision_process.start()

        self.recorder_process = mp.Process(
            name="Recorder",
            target=self.recorder_callback,
            args=(self.shm.name, recorder_receiver,)
        )
        self.recorder_process.start()

        vision_sender.close()
        recorder_sender.close()
        vision_receiver.close()
        recorder_receiver.close()

        self.output_stream = data_receiver

        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        """Exit the process context manager."""
        logger.info("Stopping Robot..")

        logger.info("Terminating processes and cleaning up shared memory...")
        try:
            for process in mp.active_children():
                logger.info(
                    f"Terminating process {process.name} (PID: {process.pid})")
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    logger.warning(
                        f"Process {process.name} (PID: {process.pid}) did not terminate gracefully, killing it.")
                    process.kill()
                    process.join(timeout=5)
                    if process.is_alive():
                        logger.error(
                            f"Process {process.name} (PID: {process.pid}) could not be killed. Manual cleanup may be required.")

            if self.shm:
                self.shm.close()
                self.shm.unlink()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.warning(
                f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
