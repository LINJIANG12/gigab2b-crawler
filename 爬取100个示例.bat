@echo off
chcp 65001 >nul
title GigaB2B - 爬取 100 个示例数据
echo ========================================================
echo        GigaB2B - 爬取 100 个示例数据测试
echo ========================================================
echo.
py -3.14 main.py --limit 100
echo.
echo 测试完成，请查看 data 目录下的 Excel 和 CSV 报表！
pause
