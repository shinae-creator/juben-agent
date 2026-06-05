@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   短剧 Agent 创作工作站
echo ========================================
echo.
echo 正在检查环境...

py --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python！请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [✓] Python 已就绪
echo.

echo 正在检查依赖...
py -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [警告] 依赖安装失败，尝试继续...
)

echo [✓] 依赖已就绪
echo.

echo 正在启动服务...
echo 浏览器打开 http://localhost:8501 即可使用
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

py -m streamlit run app.py --server.headless true --server.port 8501

pause
