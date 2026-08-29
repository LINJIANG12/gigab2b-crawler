# GigaB2B 全站商品全字段大规模数据采集系统

基于 Python 3.14 + 官方后端 API 逆向驱动的跨境大件供应链平台（GigaB2B）工业级商品数据采集与导出系统。

---

## 🌟 核心特性

- **官方 API 驱动**：直接调用官方 JSON 接口 (`product/list/search`, `product/info/info/baseInfos`, `product/info/price/list`)，速度达 **12~18 件/秒**。
- **37 个全量独立字段**：
  - **基础信息**：商品 ID、货号/SKU、商品标题、分类全路径、店铺名称、店铺代码、商品链接
  - **价格与库存**：B2B批发价、折扣价、MSRP、起订量、总现货库存、各海外分仓库存分布
  - **物流与履约**：一件代发预估运费、云仓运费区间、出库处理时效、运输派送时效、是否 LTL 大件物流、总磅重、总体积
  - **规格与属性**：主颜色、主材质、原产国、UPC 编码、产品组装尺寸、外包装箱规长宽高与毛重
  - **图文与资料**：质量评级与退货率、采购订单量、售后质保政策、说明书手册下载直链、核心卖点提要、详细描述
  - **媒体与多变体**：高清主图、全量副图（多达 15~25 张）、多变体明细（子 SKU 价格与库存）
  - **状态与诊断**：在售与权限状态、数据状态与原因说明（如全仓缺货、需申请供应商授权）
- **持久化与断点续爬**：内置 SQLite WAL 模式数据库 (`gigab2b.db`)，支持任意中断后增量继续爬取。
- **大规模分卷 Excel 与 CSV 导出**：自动分卷（每 50,000 条切卷）、UTF-8 BOM CSV、文件占用自动避让与样式自适应美化。
- **全站 217 个分类覆盖**：实测全站约 9.68 万件商品，支持全量递归扫描与多线程并发抓取。

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置登录凭据 (Cookie)
1. 在 Edge / Chrome 浏览器中打开 [https://www.gigab2b.com](https://www.gigab2b.com) 并登录。
2. 按 `F12` 打开开发者工具 -> 切换到 **Console (控制台)**。
3. 输入 `copy(document.cookie)` 并按回车。
4. 将复制的内容粘贴保存到项目根目录的 `cookie.txt` 文件中即可。

### 3. 一键运行采集

- **运行 100 条示例商品测试**：
  - 双击 `爬取100个示例.bat`，或在终端运行：
    ```bash
    py -3.14 crawl_100_samples.py
    ```
- **启动全站全量数据采集**：
  - 双击 `启动采集.bat`，或在终端运行：
    ```bash
    py -3.14 main.py --workers 20
    ```
- **查看当前数据库状态与采集进度**：
  ```bash
  py -3.14 main.py --status
  ```
- **从已有数据库重新导出 Excel/CSV 报表**：
  ```bash
  py -3.14 main.py --export-only
  ```
- **测算全站分类与商品数量分布**：
  ```bash
  py -3.14 calc_category_totals.py
  ```

---

## 📁 项目结构

```text
├── docs/                     # 逆向分析、风控绕过与技术文档
├── tools/                    # 逆向探测、数据审计、价格修复与诊断分析工具集
├── data/                     # 采集结果输出目录（Excel / CSV）
├── images/                   # 商品高清图片下载目录
├── config.py                 # 全局配置（并发数、超时、重试与路径）
├── cookie_manager.py         # Cookie 自动管理、登录态校验与 Edge 本地提取
├── database.py               # SQLite 持久化、任务队列与断点续爬管理
├── parser.py                 # 37 字段深度结构化解析器
├── crawler.py                # 全站多线程并发采集调度引擎
├── exporter.py               # Excel / CSV 结构化分卷导出模块
├── main.py                   # CLI 命令行主入口
├── crawl_100_samples.py      # 快速 100 条示例验证脚本
├── calc_category_totals.py   # 全站分类商品体量测算工具
├── cookie.txt.example        # Cookie 格式模板
├── requirements.txt          # Python 依赖清单
├── 启动采集.bat              # Windows 一键全量采集脚本
├── 爬取100个示例.bat         # Windows 一键示例采集脚本
└── 提取Edge登录凭据.bat      # Windows 一键提取 Cookie 脚本
```
