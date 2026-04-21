import sys
import platform
from src import logger


def get_camera_class():
    """
    Get the appropriate camera class for the current platform.

    :returns: AsyncCamera (PiCamera2) on Raspberry Pi, USBCamera on other platforms
    """

    is_pi = platform.system() == "Linux"

    try:
        if is_pi:
            import picamera2
            logger.info("PiCamera2 import successful, using AsyncCamera")  
            from src.modules.asyncCamera import AsyncCamera
            return AsyncCamera
        else:
            logger.warning(
                "PiCamera2 not available, falling back to USB camera")
            raise ImportError("Not on Raspberry Pi")
    except ImportError as e:
        logger.warning(
            f"Camera import failed ({e}), using USBCamera instead")
        from src.modules.usbCamera import USBCamera
        return USBCamera


def create_camera(*args, **kwargs):
    """
    Create a camera instance using the appropriate class for this platform.

    :param args: Positional arguments to pass to camera constructor
    :param kwargs: Keyword arguments to pass to camera constructor
    :returns: Camera instance (AsyncCamera or USBCamera)
    """
    CameraClass = get_camera_class()
    return CameraClass(*args, **kwargs)
