# Install

```bash
$ sudo apt-get install python3-dev
$ # git clone git@github.com:irsdkv/tlns-gui.git
$ git clone --recursive https://github.com/irsdkv/tlns-gui.git
$ cd tlns-gui
$ python3 -m venv .venv
$ source .venv/bin/activate
$ cd tinyproto
$ python setup.py install
$ cd ..
$ pip install -e .
$ deactivate
```

# Run GUI
```bash
$ cd tlns-gui
$ source  .venv/bin/activate
$ tlns_gui.py
$ deactivate
```

# Run serial test
```bash
$ cd tlns-gui
$ source  .venv/bin/activate
$ tlns_serial_testing.py data/serial_test.toml -d </serial/device/path> [-B baud]
$ deactivate
```