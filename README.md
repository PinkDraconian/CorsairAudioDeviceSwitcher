Build the executable:
```
./venv/Scripts/pyinstaller --onefile --noconsole --add-binary ".\SoundVolumeView.exe;." .\VOID_autoswitch.py
```

I then created a Windows startup task so this executable is executed whenever I log in.
