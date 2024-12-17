all: windows

windows:
	rm -rf /windows
	mkdir windows
	cp dm-cli.exe windows/dm-cli.exe
	cp dm-cli windows/dm-cli
	cp gui.py windows/gui.py
	cp dm_cli.py windows/dm_cli.py
	cp dron_motors.png windows/dron_motors.png
	cp moment_test.lua windows/moment_test.lua
	cp test_conn.lua windows/test_conn.lua
	cp cooling.lua windows/cooling.lua
	cp requirements.txt windows/requirements.txt