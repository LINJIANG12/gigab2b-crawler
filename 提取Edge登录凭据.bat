@echo off
chcp 65001 >nul
title GigaB2B - 自动提取 Edge 登录凭据
echo ========================================================
echo        GigaB2B 爬虫 - 自动提取 Edge 登录凭据
echo ========================================================
echo.
echo 注意：
echo 提取时 Edge 会独占 Cookie 数据库，请先临时关闭 Edge 浏览器。
echo.
pause
py -3.14 main.py --extract-cookie
echo.
echo 凭据提取完毕后，您可以重新打开 Edge 浏览器正常浏览！
pause
