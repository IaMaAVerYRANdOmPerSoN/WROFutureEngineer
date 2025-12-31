---
layout: page
title: "AsyncCamera"
permalink: /AsyncCamera
---

# class [AsyncCamera](/AsyncCamera)

An asynchronous wrapper for the `picamera2` Library

## Methods

### `__init__(self, config = {"format": "YUV420", "size": (160, 120)})`
The constructor for the AsyncCamera class.

> **Warning!**   
> The constructor does not initialize or open hardware. Hardware resource initialization is done asynchronously in `__aeneter__`. The correct way to interface with an instance of `AsyncCamera` is through an `async with AsyncCamera()...` block

**Parameters:**  
`self`: The instance of `AsyncCamera`.
`config`: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.

**Returns:**
`self`, an initialized instance of [`AsyncCamera`](/AsyncCamera).

**Code**  
```py
def __init__(self, config = {"format": "YUV420", "size": (160, 120)}):
    """
    The constructor for the AsyncCamera class.
    
    :param self: The instance of `AsyncCamera`.
    :param config: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.
    """
    self._config = config
    self._cam = None
    self.FRAMERATE = 30

    self.failiures = 0
    self.loop = asyncio.get_event_loop()
    self.executor = None
```
---

### `__aenter__(self)`
Initializes hardware resources defined in `__init__` asynchronously.

**Parameters:**  
`self`: The instance of `AsyncCamera`.

**Returns**  
`self`: The instance of `AsyncCamera`.

**Code**  
```py
async def __aenter__(self):
    """
    Initializes hardware resources defined in __init__ asyncrounously.

    :param self: The instance of `AsyncCamera`.
    :raises: `ConnectionError` if an execption occurs or the camera times out.
    """
    self.executor = ThreadPoolExecutor(10) 
    
    try:
        self._cam = await asyncio.wait_for(
            self.loop.run_in_executor(self.executor, picamera2.Picamera2), 
            timeout=2.0
        )

        config = self._cam.create_preview_configuration(main=self._config)

        await asyncio.wait_for(
            self.loop.run_in_executor(self.executor, self._cam.configure, config),
            timeout=1.0
        )
        await asyncio.wait_for(
            self.loop.run_in_executor(self.executor, self._cam.start),
            timeout=1.0
        )

        return self

    except (asyncio.TimeoutError, Exception) as e:
        logger.critical(f"Camera Hardware Initialization Failed: {e}")
        raise ConnectionError("Camera not responding during power-up.") from e
```
---

### `__aexit__(self)`
Gracefully closes hardware resources asynchronously.

**Parameters:**  
`self`: The instance of `AsyncCamera`.

**Returns**  
`None`

**Code**
```py
async def __aexit__(self, *args): # Let the main loop handle the logging and execeptions
    if hasattr(self, "_cam") and self._cam:
        await self.loop.run_in_executor(self.executor, self._cam.stop)
    
    if hasattr(self, "executor") and self.executor:
        self.executor.shutdown(wait=False)
```

### `get_frame_async(self, timeout = 0.2)`
Fetch a frame asynchronously from `self._cam`

**Parameters**  
`self`: The instance of `AsyncCamera`  
`timeout`: The maximum roundtrip time, in seconds, before raising `asyncio.TimeoutError`

**Returns**  
`frame`: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.  
`"IO_ERR"`: If communication fails ten consecutive times, to avoid queue too many threads into `self.executor`

**Code**
```py
async def get_frame_async(self, timeout = 0.2):
    """
    Fetch a frame asyncronously from `self._cam`
    
    :param self: The instance of `AsyncCamera`
    :param timeout: The maximum roundtrip time, in seconds, before raising asyncio.TimeoutError
    :returns: frame: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.
    """
    while self.failiures <= 10:
        try:
            frame = await asyncio.wait_for(self.loop.run_in_executor(self.executor, self._cam.capture_array()), timeout)
            self.failiures = 0
            logger.info(f"Fetched new frame from PiCamera sucessfully")
            return frame
        
        except asyncio.TimeoutError:
            self.failiures += 1
            if self.failiures >= 10: 
                raise MemoryError("Garbage threads have bulit up beyond safe threshold.") from asyncio.TimeoutError
            logger.error(f"Timed out awaiting video stream")

        except Exception as e:
            self.failiures += 1
            if self.failiures >= 10: 
                raise IOError("Unacceptable buildup of IOerrors, last error: '{e}'")
            logger.error(f"Caught video stream exception: '{e}'")
        
        return "IO_ERR"
```
---

### `buffer_frames_async(self, num_frames = 5, timeout = 1.0)`
Buffers `num_frames` frames asynchronously.

**Parameters**

`self`: The instance of `AysncCamera`.  
`num_frames`: The number of frames to buffer.  
`timeout`: Global timeout for buffering frames.  

**Returns**  
`list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.

**Code**
```py
async def buffer_frames_async(self, num_frames = 5, timeout = 1.0):
        """
        Buffers `num_frames` frames asynchronously.
        
        :param self: The instance of `AysncCamera`.
        :param num_frames: The number of frames to buffer.
        :param timeout: Global timeout for buffering frames.
        :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
        """
        return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]
```
---

### `stream(self)`
asynchronous indefinite yield camera IOstream.
        
**Parameters**  
`self`: The instance of AsyncCamera.

**Yields**  
`tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.

**Returns**  
`None`

**Code**
```py
    async def stream(self):
        """
        asynchronous indefinite yield camera IOstream.
        
        :param self: The instance of AsyncCamera.
        :yields: `tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.
        :returns: `None`
        """
        while True:
            frame = await self.get_frame_async()
            if frame is not None:
                yield frame

            await asyncio.sleep(1/self.FRAMERATE - 0.05)
```
---

## Attributes

### `self._config`  
A `picamera2` configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration`

### `self._cam`  
A `picamera2.Picamera2` object, used for directly interfacing with the CSI Camera.

### `self.FRAMERATE`  
A constant representing target frame throughput for the `stream` method.

### `self.failures`
A counter representing the number of consecutive failed `get_frame_async()` calls.

### `self.loop`
The running `asyncio` `AbstractEventLoop`, for creating and managing pooled executors.

### `self.executor`
A `concurrent.futures` `ThreadPoolExecutor(10)`, for desynchronizing blocking IO operations.

<!--- Some way to make footers without reapeating I'm sure --->