# Cloudflare Pages + Tunnel 部署指南

## 架构概览

```
用户浏览器访问                Cloudflare Pages                 你的本地服务器
https://ltr.pages.dev              │                              │
         │                         │                              │
         ▼                         ▼                              ▼
    index.html ──────────►  _redirects  ─────────────────►  cloudflared tunnel
    (ECharts UI)              /api/* → tunnel                  localhost:8000
                              /health → tunnel                (FastAPI + NumPy)
                                                            (8,000笔贷款数据)
```

- **静态页面**（HTML/CSS/JS）→ Cloudflare Pages 全球 CDN 加速
- **API 请求**（模拟计算）→ 通过 `_redirects` 代理到你的本地 tunnel → 你的电脑运行 Python 计算

---

## 第一步：把前端部署到 Cloudflare Pages

### 方法一：通过 GitHub 自动部署（推荐）

1. 确保代码已推送到 GitHub：https://github.com/Shine648/Auto-Finance-LTR-Simulation
2. 登录 Cloudflare Dashboard → Workers & Pages → Pages
3. 点击 **"Connect to Git"** → 选择 `Shine648/Auto-Finance-LTR-Simulation`
4. 构建设置：
   - **Framework preset**: None
   - **Build command**: 留空
   - **Build output directory**: `frontend` ← 重点！
5. 点击 **"Save and Deploy"**

部署完成后你会得到一个域名，例如 `https://auto-finance-ltr-simulation.pages.dev`

### 方法二：手动上传 frontend 文件夹

1. 进入 Cloudflare Pages → "Upload assets" → 上传 `frontend/` 整个目录
2. Pages 会自动识别 `_redirects` 文件

---

## 第二步：在你电脑上运行后端 + Tunnel

```bash
# 1. 确保后端运行
cd d:\project for school\credit_sim
python main.py

# 2. 新开一个终端，启动 tunnel
cloudflared tunnel --url http://localhost:8000
```

你会看到类似输出：
```
Your quick Tunnel has been created!
https://violations-desert-proposed-modules.trycloudflare.com
```

**复制这个 tunnel URL。**

---

## 第三步：配置 _redirects

编辑 `frontend/_redirects` 文件，把 tunnel URL 替换进去：

```diff
- /health  https://your-tunnel.trycloudflare.com/health  200
+ /health  https://violations-desert-proposed-modules.trycloudflare.com/health  200
```

重新部署 Pages 即可。

---

## 第四步：验证

打开你的 Pages 域名（例如 `https://auto-finance-ltr-simulation.pages.dev`）：
- ✅ 页面加载正常（深色主题 ECharts 面板）
- ✅ 右上角连接状态显示绿色 "Connected"
- ✅ 点击 "Run Full 8-Year Cycle" 能正常跑出结果

---

## 关于 _redirects 文件

```apache
# API 路由 → 转发到你的本地 tunnel
/health       https://xxx.trycloudflare.com/health       200
/macro-cycle  https://xxx.trycloudflare.com/macro-cycle  200
/simulate     https://xxx.trycloudflare.com/simulate     200

# 所有其他请求 → 返回 index.html（SPA 模式）
/*            /index.html                                 200
```

- `200` 表示"代理模式"（不改变 URL，用户看到的是你的 Pages 域名）
- 每次 tunnel URL 变化时只需更新此文件重新部署

---

## 注意事项

| 事项 | 说明 |
|------|------|
| **Tunnel URL 变化** | TryCloudflare 每次重启都会生成新的 URL，需要更新 `_redirects` |
| **固定域名方案** | 注册 Cloudflare 账号 → 创建命名 Tunnel → 绑定自己的域名 |
| **延迟** | API 请求需要经过 Cloudflare → 你的电脑，首次请求约 1-3 秒 |
| **并发** | 免费 tunnel 有连接数限制，适合演示和测试 |
| **数据安全** | 数据只在你本地计算，tunnel 只传输加密的 API 请求 |

## 一键启动脚本（本地）

```batch
@echo off
cd /d "%~dp0"
echo Starting backend...
start python main.py
timeout /t 3 /nobreak >nul
echo Starting tunnel...
cloudflared tunnel --url http://localhost:8000