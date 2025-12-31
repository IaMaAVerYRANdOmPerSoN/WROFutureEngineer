---
layout: page
title: "Client"
permalink: /Client
---

# class [AsyncCamera](/AsyncCamera)

An asynchronous remote procedure call (RPC) over serial.

## Methods

### `__init__(self, port='/dev/ttyACM0', baud = 115200, timeout=0.3, log = "log.txt", log_verbose = "verbose.txt")`

The Constructor for the `Client` class.
> **Warning!**   
> The constructor does not initialize or open hardware. Hardware resource initialization is done asynchronously in `__aeneter__`. The correct way to interface with an instance of `Client` is through an `async with Client()...` block

**Parameters**
`Self`: 
The instance of Client  
`Port`  
The serial port passed to `aioserial.AioSerial`.  
`baud`  
The buadrate of the serial protocol.  
`timeout`  
Default timeout for granular requests.  
`log`  
path to write standard logs to, along with `sys.stderr`.  
`log_verbose`  
path to write verbose logs to.

**Returns**  
`self`: An instance of `Client`

**Code**
```py
def __init__(self, port='/dev/ttyACM0', baud = 115200, timeout=0.3, log = "log.txt", log_verbose = "verbose.txt"):
    """
    The constructor for the `Client` class
    
    :param self: The instance of Client
    :param port: The serial port passed to `aioserial.AioSerial`.
    :param baud: The buadrate of the serial protocol.
    :param timeout: Default timeout for granular requests.
    :param log: path to write standard logs to, along with `sys.stderr`.
    :param log_verbose: path to write verbose logs to.

    :returns self: an instance of `Client`
    """
    logger.remove()
    fmt = (
        "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
        "<cyan>{line:03}: {function: <18}</cyan> │ "
        "<level>{level: <8}</level> │ "
        "<level>{message}</level>")
    logger.add(sys.stderr, level="WARNING", format=fmt)
    logger.add(log, level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)
    logger.add(log_verbose, level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt, backtrace=True, diagnose=True)
    
    self.SERIAL = None
    self.port, self.baud = port, baud
    self.DEFAULT_TIMEOUT = timeout
    self.TIDS = cycle([i for i in range(1, 501)])
    self.WHEELBASE = 0.1 
    self.MAX_SPEED = 8
    self.WAIT_RE = re.compile(r"WAITMS ([0-9]+)")
    self.is_connected = False
    self.loop = asyncio.get_event_loop()
    self._pending_requests = {} # {TID: future} -> {TID: response}
    self.servo_angle = 0
    self.encoder_value = 0

    logger.info(f"======= CLIENT INSTANCE STARTED: Port = {port}, Baud = {baud}, Timeout = {timeout} ======= ")
```

### `__serial_listener(self)`
A background asynchronous serial listener that resolves serial IO dependent futures.
        
**Parameters**

`self`  
The instance of `Client`

**Returns**

`NoReturn`

**Code**
```py
async def __serial_listener(self):
    """
    A background asynchronous serial listener that resolves serial IO dependent futures.
    
    :param self: The instance of `Client`
    :return: `NoReturn`

    """
    while True:
        line = await self.SERIAL.readline_async()
        response = line.decode('utf-8').strip()

        logger.debug(f"Line read from serial buffer: '{response}'")
        
        parts = response.split(" ", 1)
        if len(parts) < 2: continue
        
        tid, message = parts[0], parts[1]
        
        if tid in self._pending_requests:
            future = self._pending_requests[tid]
            if not future.done():
                future.set_result((tid, message))
```

## `__aenter__(self)`