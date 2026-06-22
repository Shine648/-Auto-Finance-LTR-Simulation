# Auto-Finance-LTR-Simulation

一个基于宏观经济周期的汽车金融组合损失率（LTR）模拟平台。该工具利用 Vasicek-Merton 信用风险模型，结合 8 年宏观周期数据（GDP、失业率、房价），对 8,000 笔贷款组合进行蒙特卡洛模拟，帮助金融机构动态预测预期损失（Expected Loss）、风险敞口（Exposure）及在险价值（VaR 99%）。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **📊 蒙特卡洛模拟** | 多因子 Merton/Probit 模型，10,000 次迭代 |
| **📈 8 年宏观周期** | Expansion → Peak → Recession → Trough → Recovery |
| **🔥 双重压力热力图** | 交互式 Plotly 热力图，失业率 × 资产价格共振分析 |
| **📄 PDF 报告导出** | ReportLab 后端渲染，含图表、指标表、局限性声明 |
| **🌐 公网部署** | Cloudflare Pages + Tunnel，全球 CDN 加速 |

## 🚀 快速开始

```bash
# 1. 启动后端
cd credit_sim
uvicorn main:app --host 127.0.0.1 --port 8000

# 2. 打开浏览器
# 访问 http://127.0.0.1:8000/
```

或双击 `credit_sim/start_local.bat` 一键启动。

## 🌍 公网部署

详见 [CLOUDFLARE_DEPLOY.md](credit_sim/CLOUDFLARE_DEPLOY.md)

### 架构
```
用户浏览器 → Cloudflare Pages CDN (静态文件)
           → cloudflared tunnel → 本地 FastAPI (计算引擎)
```

### 步骤
1. 安装 cloudflared
2. 运行 `credit_sim/start_tunnel.bat`
3. 复制生成的 `https://xxx.trycloudflare.com` URL
4. 在 Cloudflare Pages 控制台设置 `TUNNEL_URL` 环境变量
5. 推送到 GitHub → Pages 自动部署

## 🧩 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/presets` | GET | 预设场景列表 |
| `/macro-cycle` | GET | 8 年宏观周期 |
| `/simulate` | POST | 单场景模拟 |
| `/simulate/cycle` | POST | 全周期模拟 |
| `/simulate/batch` | POST | 批量场景对比 |
| `/simulate/heatmap` | POST | 双重压力热力图 |
| `/sensitivity/gdp` | GET | GDP 敏感度曲线 |
| `/report/pdf` | POST | 导出 PDF 报告 |

## 📁 项目结构

```
credit_sim/
├── main.py                 # FastAPI 后端
├── models.py               # Pydantic 模型
├── engine/
│   ├── simulation.py       # 蒙特卡洛 + Vasicek 引擎
│   ├── factors.py          # 宏观变量→因子映射
│   ├── macro_cycle.py      # 8 年周期定义
│   ├── heatmap.py          # 双重压力热力图引擎
│   ├── pdf_report.py       # PDF 报告生成器
│   ├── metrics.py          # 风险指标计算
│   └── cache.py            # 缓存层
├── data/portfolio.json     # 贷款组合数据
└── start_local.bat         # 本地启动脚本

frontend/
├── final.html              # 主仪表盘
├── _redirects              # Cloudflare Pages 路由
└── functions/
    └── _middleware.js      # API 代理中间件
```
