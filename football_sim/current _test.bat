@echo off
echo ========================================
echo  Football Sim - Test Suite
echo ========================================
echo.
python -m pytest tests/test_ai_tactics.py -v -s
echo.
echo ========================================
pause