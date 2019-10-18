REM ensure the correct python (virtual) environment is active when executing
pyinstaller --onefile ^
	--icon=".\_icon\scaleify.ico" ^
	buildshapeify.py
copy buildshapeify.py .\dist\