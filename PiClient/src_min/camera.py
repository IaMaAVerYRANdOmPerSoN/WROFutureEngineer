import numpy as np
from loguru import logger
import picamera2 # type: ignore TODO: Get the .pyi file from the picamera2 repo and add it to the project so my stuff gets linted.

class Camera():
    def __init__(self, config = {"format": "YUV420", "size": (512, 384)}):
        """
        The constructor for the Camera class.
        
        :param self: The instance of `Camera`.
        :param config: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.
        """
        self._config = config
        self._cam = None
        self.INITIAL_ROI = 100 # Let's say drop top 100 pixels, will add dynamic runtime tuning hopefully
        

    def __enter__(self):
        """
        Initializes hardware resources defined in __init__.

        :param self: The instance of `Camera`.
        :raises: `ConnectionError` if an exception occurs or the camera times out.

        :returns: `self`: the instance of `Camera`
        """
        
        try:
            self._cam = picamera2.PiCamera2()
            sensor_config = {
                "output_size": (640, 480),
                "bit_depth": 10
            }
            controls_config = {
                "FrameDurationLimits": (33333, 33333), 
                "AeEnable": True, 
            }
            config = self._cam.create_preview_configuration(
                main=self._config,
                sensor=sensor_config,
                raw=None,
                controls=controls_config,
                buffer_count=2,
            )

            self._cam.configure(config)
            self._cam.start()

            logger.info(f"Camera configuration applied: {self._cam.camera_configuration()}")
            return self
    
        except (Exception) as e:
            logger.critical(f"Camera Hardware Initialization Failed: {e}")
            raise ConnectionError("Camera not responding during power-up.") from e

    def __exit__(self, *args): # Let the main loop handle the logging and exceptions
        if hasattr(self, "_cam") and self._cam:
            self._cam.stop()
            self._cam.close()
            self._cam = None
        
    def get_frame(self):
        """
        Fetch a frame from `self._cam`
        
        :param self: The instance of `Camera`.
        :returns: frame: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.
        """
        
        while True:
            try:
                frame: np.ndarray = self._cam.capture_array()
                
                frame = frame.flatten()
                y_end = 512*384
                u_end = y_end + (256*192)

                y_plane = frame[:y_end].reshape((384, 512))
                u_plane_raw = frame[y_end:u_end].reshape((192, 256))
                v_plane_raw = frame[u_end:].reshape((192, 256))

                y_plane = y_plane[self.INITIAL_ROI:, :]
                u_plane_raw = u_plane_raw[self.INITIAL_ROI//2:, :]
                v_plane_raw = v_plane_raw[self.INITIAL_ROI//2:, :]

                u_plane = u_plane_raw.repeat(2, axis=0).repeat(2, axis=1)
                v_plane = v_plane_raw.repeat(2, axis=0).repeat(2, axis=1)

                full_yuv = np.dstack((y_plane, u_plane, v_plane))

                logger.info(f"Fetched new frame from PiCamera successfully")
                return full_yuv.astype(np.uint8)
                
            except TimeoutError:
                logger.warning("Camera frame capture timed out, retrying...")

            except Exception as e:
                logger.warning(f"Unexpected error during frame capture: {e}, continuing...")

    def buffer_frames(self, num_frames = 5):
            """
            Buffers `num_frames` frames.
            
            :param self: The instance of `Camera`.
            :param num_frames: The number of frames to buffer.
            :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
            """
            return [self.get_frame() for _ in range(num_frames)]