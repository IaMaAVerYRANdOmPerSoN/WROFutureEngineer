# Contributing

Before contributing to this project, please discuss the change you wish to make via issue, email, or any other method with the owners of this repository before making a change. This is not a strict requirement, but it is highly recommended as it helps to avoid unnecessary work and ensures that your contributions align with the project's goals.

## Environment setup

> [!NOTE]
> Please note that neither the built wheel nor the editable install will function as intended on non-Raspberry Pi OS (64-bit) Bookworm or later platforms. If you want to run the software on a different platform, you will need to modify the source code and build a compatible wheel for that platform.
>
> It is strongly recommended to use system-installed `picamera2` on Raspberry Pi OS (64-bit) Bookworm or later. picamera2 needs access to Raspberry Pi's proprietary libcamera stack, which is not available on other platforms.

Install packages using editable installs:

```bash
cd WROFutureEngineer
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e PiClient/piclient-core -e PiClient/piclient-open_challenge -e PiClient/piclient-obstacle_challenge -e PiClient/piclient-cli
```

If you want to test the built wheel, use `--system-site-packages` when creating the virtual environment to access the system-installed `picamera2`:

```bash
python3 -m venv --system-site-packages .venv
```

If you are building documentation, you will also need to install the following dependencies:

```bash
pip install sphinx furo
```

Automated CI will deploy the documentation to firebase when changes are pushed to the `main` branch. You can also build the documentation locally by running:

```bash
cd PiClient/docs
make html # Or use `make.bat html` on Windows
```

## Guidelines

We do not use automated pre-commit hooks, or code formatters like black or isort. However, we do require that all code is formatted according to PEP 8 guidelines. Please ensure that your code adheres to these guidelines before submitting a pull request, and use a code formatter if necessary. (I personally use the autopep8 VS Code extension, which is very convenient.)

Please update SemVer strings everywhere in the codebase when making changes that affect the public API. This includes updating the version number in all `pyproject.toml` files, as well as any other files that reference the version number. Please also update the changelog to reflect your changes.

As 100% accurate SemVer versioning is [impossible to achieve](https://iscinumpy.dev/post/bound-version-constraints/#:~:text=like%20JavaScript%E2%80%99s%20npm.-,SemVer,that%20does%20mean%20there%20is%20no%20such%20thing%20as%20%E2%80%9Cpure%E2%80%9D%20SemVer.,-Example%3A%20pyparsing%203.0.5), apply reasonable judgment when determining whether a change is a major, minor, or patch change. If you are unsure, please discuss the change with the maintainers before submitting a pull request.

Checks that do not pass on the CI will not be merged. Please ensure that your code passes all checks before submitting a pull request. (And update the tests if necessary.)