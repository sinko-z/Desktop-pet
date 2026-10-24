@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安装 Desktop Pet 依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo 安装失败，请确认已安装 Python 3.10 及以上版本并加入 PATH。
  pause
  exit /b 1
)
echo 安装完成，双击 run.bat 即可启动。
pause
