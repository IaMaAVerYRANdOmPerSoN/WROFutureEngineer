# Setup

> [!NOTE]
> This guide assumes you are using a Raspberry Pi with at least 4GB of RAM, running Raspberry Pi OS (64-bit) Bookworm or later. If you are using a different OS or hardware, these instructions may not work, and you may need to adapt them to your environment. We cannot provide support for non-Raspberry Pi OS systems.
>
> Python, `pip`, and picamera2 are bundled with Raspberry Pi OS (64-bit) Bookworm or later. If you are using a different OS, you will need to install these dependencies manually.
>
> If you want to build the software from source, see [Building from Source](./building_from_source.md). We recommend using the prebuilt wheel for most use cases.

## Hardware Setup

First, you should assemble the robot according to the instructions in [Hardware Assembly](./hardware_assembly.md). Please make sure to follow the assembly instructions carefully, as improper assembly can lead to hardware damage or malfunction. Please ensure all electrical connections are secure and insulated, and that the robot is powered off when making adjustments.

## Software Setup

After building the robot and imaging the Raspberry Pi, you can set up the software on the Pi. The easiest way is to use the prebuilt wheel. `pip` (or equivalent) will automatically install the wheel and its dependencies.

If you want to build from source, see [Building from Source](./building_from_source.md).

> [!WARNING]
> picamera2 is not a dependency of the wheel. We strongly recommend using the system-wide installation, which is included in the Raspberry Pi OS image.
> If you are using a virtual environment, use `--system-site-packages` option to access the system-installed picamera2.
>
> picamera2 is not supported on non-Raspberry Pi OS systems. Picamera2, and by extension our software, will not work without Raspberry Pi's libcamera binaries.
> Please do not attempt to install picamera2 from source or use a different camera library; We cannot provide support for these configurations.

Install the `piclient` package, and its optional dependencies with your preferred package manager. For example, using pip/venv: <!-- Replace with link once published to PyPI -->

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install piclient[all]
```

That's it! You can now run the open challenge with `wro` or the obstacle challenge with `wro --GeneralConfig.CHALLENGE obstacle`. For more information on configuration and tuning, see [Configuration and Tuning](../03_software/config.md).
