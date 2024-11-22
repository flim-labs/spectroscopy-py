py -3.9 -m venv .venv-spectroscopy
.venv-spectroscopy\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r .\requirements.txt
pip install flim_labs-1.0.67-cp39-none-win_amd64.whl --force-reinstall
pip install PyQt6 --force-reinstall
pyinstaller --onefile --icon .\assets\spectroscopy-logo.ico --add-data "assets/*:assets" --add-data "export_data_scripts/*:export_data_scripts" --hidden-import=matplotlib.backends.backend_ps --hidden-import=matplotlib.backends.backend_agg .\spectroscopy.py
deactivate
