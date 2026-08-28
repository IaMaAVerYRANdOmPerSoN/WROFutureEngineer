# Building from Source

> [!NOTE]
> This guide assumes you have a working Python 3.13+ environment and are familiar with basic Python packaging and virtual environments. If you are new to Python packaging, consider reading the [Python Packaging User Guide](https://packaging.python.org/en/latest/).
>
> For developers who want to contribute to the project, we strongly recommend using editable installs (i.e., `pip install -e .`) for development. This allows you to make changes to the source code and have them reflected immediately without needing to rebuild the wheel each time. This guide is primarily for users who want to build the wheel for distribution or deployment, rather than for development purposes. Please refer to our [Development Guide](/CONTRIBUTING.md) for instructions on setting up a development environment and using editable installs.
>
> This guide works with any operating system that supports Python 3.13+, but the built wheel is only compatible with Raspberry Pi OS (64-bit) Bookworm or later. You can build the wheel on any platform, but it will only run on Raspberry Pi OS (64-bit) Bookworm or later. If you want to run the software on a different platform, you will need to modify the source code and build a compatible wheel for that platform.
>
> On Raspberry Pi OS (64-bit) Bookworm or later, you can use the prebuilt wheel instead of building from source. See [Setup Guide](./setup_guide.md) for instructions.

## Building the wheel

Clone the repository and navigate to the root directory:

```bash
git clone https://github.com/IaMaAVerYRANdOmPerSoN/WROFutureEngineer.git
cd WROFutureEngineer
```

Create a virtual environment and install the build dependencies:

```bash
python3 -m venv .venv # If you intend to test the built wheel, use --system-site-packages to access the system-installed picamera2
source .venv/bin/activate
pip install --upgrade pip build
```

Navigate to each namespace directory and build the wheel:

```bash
cd PiClient
python -m build piclient-core
python -m build piclient-open_challenge
python -m build piclient-obstacle_challenge
python -m build piclient-cli
```

You should now have a `dist` directory in each namespace with a built .whl (wheel) file, and a source distribution .tar.gz file! You can now install the wheel with pip:

```bash
# Return to the repository root to install all wheels
cd ..
pip install PiClient/*/dist/*.whl
```