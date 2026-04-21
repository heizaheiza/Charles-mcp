@echo off
chcp 65001 >nul 2>&1

:: 设置 Python UTF-8 环境
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 切换到项目目录
cd /d "E:\project\Charles-mcp"

:: 启动 MCP Server (-u 参数禁止输出缓冲)
"E:\project\Charles-mcp\venv\Scripts\python.exe" -u "E:\project\Charles-mcp\charles-mcp-server.py"
