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
    """Manage camera, vision, and recorder subprocesses around shared memory.

    Entering creates the configured shared-memory segment and starts the three
    callback processes connected by multiprocessing pipes. Exiting terminates
    those processes and releases the shared resources.

    :cvar _DEFAULT_SHM_SIZE: Default shared-memory allocation in bytes.
    :cvar _DEFAULT_SHM_NAME: Default shared-memory segment name.
    """
    _DEFAULT_SHM_SIZE: int = GLOBAL_CONFIG().CameraConfig.SHM_SIZE
    _DEFAULT_SHM_NAME: str = GLOBAL_CONFIG().SharedChallengeConfig.SHM_NAME
    _STUB_RECORDER_CALLBACK = None

    @overload
    def __init__(
        self,
        camera_callback: Callable[[_S, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[_S, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[
            _S, "Connection[Any, Any]"], NoReturn | None] | None = None,
        shm_size: int | None = None,
        shm_name: _S = ...
    ) -> None:
        """Declare the typed shared-memory-name overload for initialization."""
        ...

    @overload
    def __init__(
        self,
        camera_callback: Callable[[str, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[str, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[
            str, "Connection[Any, Any]"], NoReturn] | None = None,
        shm_size: int | None = None,
        shm_name: None = None
    ) -> None:
        """Declare the typed default-name overload for initialization."""
        ...

    def __init__(
        self,
        camera_callback: Callable[[Any, "Connection[Any, Any]"], NoReturn | None],
        vision_callback: Callable[[Any, "Connection[Any, Any]", "Connection[Any, Any]"], NoReturn | None],
        recorder_callback: Callable[[
            Any, "Connection[Any, Any]"], NoReturn | None] | None = None,
        shm_size: int | None = None,
        shm_name: Any = None
    ):
        """Initialize the fixed camera/vision/recorder process topology.

        The camera callback receives the shared-memory name and two send-only
        pipe endpoints (vision and recorder). The vision callback receives the
        name, a frame-notification receiver, and a results sender. The optional
        recorder callback receives the name and recorder receiver.

        :param shm_size: Shared-memory allocation in bytes; defaults to the
            configured camera buffer size.
        :param shm_name: Shared-memory name; defaults to the challenge name.
        :param camera_callback: Camera subprocess target.
        :param vision_callback: Vision subprocess target.
        :param recorder_callback: Recorder subprocess target, or ``None`` to
            use the stub callback.
        """
        self.shm_size = shm_size if shm_size is not None else self._DEFAULT_SHM_SIZE
        self.shm_name = shm_name if shm_name is not None else self._DEFAULT_SHM_NAME
        self.camera_callback = camera_callback
        self.vision_callback = vision_callback
        self.recorder_callback = recorder_callback if recorder_callback is not None else self._STUB_RECORDER_CALLBACK

        self.shm = None
        self.camera_process = None
        self.vision_process = None
        self.recorder_process = None
        self.output_stream = None

    @staticmethod
    def _stop_process(process: mp.Process, *, timeout: float = 2.0, kill_timeout: float = 5.0) -> None:
        """Terminate a subprocess, escalating to kill after a grace period.

        :param process: Process to terminate.
        :param timeout: Seconds to wait for graceful termination.
        :param kill_timeout: Seconds to wait after forceful termination.
        :returns: ``None``.
        :rtype: None
        """
        logger.info(f"Terminating process {process.name} (PID: {process.pid})")
        process.terminate()
        process.join(timeout=timeout)
        if process.is_alive():
            logger.warning(
                f"Process {process.name} (PID: {process.pid}) did not terminate gracefully, killing it.")
            process.kill()
            process.join(timeout=kill_timeout)
            if process.is_alive():
                logger.error(
                    f"Process {process.name} (PID: {process.pid}) could not be killed. Manual cleanup may be required.")

    def __enter__(self):
        """Create shared memory, pipes, and all three subprocesses.

        A stale segment with the configured name is closed and unlinked before
        recreation. The returned manager exposes the vision result receiver as
        :attr:`output_stream`.
        """
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
        """Stop camera and vision, wait for recorder, and unlink shared memory.

        Camera and vision receive bounded graceful termination followed by kill
        escalation. The recorder is joined without a timeout, so cleanup can
        block while it drains its pipe and closes its recording.
        """
        logger.info("Stopping Robot..")

        logger.info("Terminating processes and cleaning up shared memory...")
        try:
            for process in (self.camera_process, self.vision_process):
                if process is not None:
                    self._stop_process(process)

            if self.recorder_process is not None:
                logger.info(
                    f"Waiting for recorder process {self.recorder_process.name} (PID: {self.recorder_process.pid}) to exit cleanly")
                # Wait indefinitely for the recorder process to finish since processing usually takes as long as runtime. The user can always terminate the recorder process with Ctrl+C if it hangs for too long.
                # (hanging for a very long time is normal in this context.)
                # TODO: Make CLI more interactive to avoid confusion.
                self.recorder_process.join()

            if self.shm:
                self.shm.close()
                self.shm.unlink()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.warning(
                f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
