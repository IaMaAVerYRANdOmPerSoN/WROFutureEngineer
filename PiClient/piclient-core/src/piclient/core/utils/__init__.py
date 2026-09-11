from typing import Any

import asyncio
from multiprocessing.connection import Connection as PipeConnection
from collections.abc import AsyncGenerator

from ..lib import export


@export
async def async_pipe_reader(receiver: PipeConnection) -> AsyncGenerator[Any, None]:
    """
    Asynchronously read from a multiprocessing pipe connection, latest wins.
    """
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    latest = None

    try:
        data_event = asyncio.Event()
        loop.add_reader(receiver.fileno(), data_event.set)

        try:
            while True:
                try:
                    while receiver.poll():
                        latest = receiver.recv()
                except (EOFError, OSError):
                    return
                
                if latest is not None:
                    yield latest
                    latest = None

                data_event.clear()
                await data_event.wait()

        finally:
            loop.remove_reader(receiver.fileno())

    except NotImplementedError:  # Non-POSIX
        while True:
            try:
                data = await loop.run_in_executor(None, receiver.recv)
            except (EOFError, OSError):
                break
            yield data


@export
async def async_pipe_reader_fifo(receiver: PipeConnection) -> AsyncGenerator[Any, None]:
    """
    Asynchronously read from a multiprocessing pipe connection in FIFO order.
    """
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    try:
        data_event = asyncio.Event()
        loop.add_reader(receiver.fileno(), data_event.set)

        try:
            while True:
                try:
                    while receiver.poll():
                        yield receiver.recv() # Yeild all queued data before waiting for the next event.
                except (EOFError, OSError):
                    return

                data_event.clear()
                await data_event.wait()

        finally:
            loop.remove_reader(receiver.fileno())

    except NotImplementedError:  # Non-POSIX
        while True:
            try:
                data = await loop.run_in_executor(None, receiver.recv)
            except (EOFError, OSError):
                break
            yield data