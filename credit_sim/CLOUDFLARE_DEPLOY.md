# Cloudflare Pages + Tunnel — Dual Routing 部署指南

## 架构概览 (Dual Routing)

```
用户浏览器访问 Cloudflare Pages               Cloudflare CDN          你的本地服务器
                            │                      │                     │
                            ▼                      ▼                     ▼
                    ┌───────────────┐      ┌──────────────┐     ┌──────────────┐
                    │  Static Routes │─────▶│  CDN Edge    │     │  localhost:8000 │
                    │  /index.html   │      │  (Fast!)     │     │  (FastAPI)   │
                    │  /tunnel-config│      └──────────────┘     │  NumPy引擎  │
                    │  /static/*     │                           │  40,000贷款  │
                    └───────────────┘                           └──────┬───────┘
                                                                        │
                    ┌───────────────┐      ┌──────────────┐            │
                    │  Dynamic Routes│─────▶│  cloudflared │────────────┘
                    │  /api/*        │      │  tunnel      │
                    │  /simulate     │      └──────────────┘
                    │  /health       │
                    │  /macro-cycle  │
                    └───────────────┘
```

**核心思想：**
- **静态内容**（HTML/CSS/JS）→ Cloudflare Pages CDN 全球加速，零延迟
- **动态 API**（模拟计算）→ 通过 tunnel 代理到你的本地 Python 后端
- **配置界面** → `/tunnel-config` 页面可动态生成 `_redirects`

---

## 快速开始（本地测试 + 部署）

### 第一步：启动本地服务 + Tunnel

```batch
# 一键启动所有服务
start_public.bat
```

或者分别启动：
```batch
# 终端 1：启动后端
start_local.bat

# 终端 2：启动 tunnel
start_tunnel.bat
```

启动后你会看到类似输出：
```
Your quick Tunnel has been created!
https://violations-desert-proposed-modules.trycloudflare.com
```

**复制这个 tunnel URL。**

### 第二步：配置 Tunnel URL

1. 打开浏览器访问 http://localhost:8000/tunnel-config
2. 粘贴你的 tunnel URL（如 `https://xxx.trycloudflare.com`）
3. 点击 **"Save Tunnel URL"**
4. 点击 **"Generate Config"**
5. 点击 **"📋 Copy"** 复制生成的 `_redirects` 内容

### 第三步：部署到 Cloudflare Pages

#### 方法一：通过 GitHub 自动部署（推荐）

1. 推送代码到 GitHub：https://github.com/Shine648/Auto-Finance-LTR-Simulation
2. 登录 Cloudflare Dashboard → Workers & Pages → Pages
3. 点击 **"Connect to Git"** → 选择你的仓库
4. 构建设置：
   - **Framework preset**: None
   - **Build command**: 留空
   - **Build output directory**: `frontend` ← 重点！
5. 点击 **"Save and Deploy"**
6. **部署后**：在 Pages Dashboard → **Environment variables** 添加：
   - `TUNNEL_URL` = `https://你的-tunnel-url.trycloudflare.com`
   - 或者：在 `frontend/_redirects` 中取消注释并填写 tunnel URL

#### 方法二：手动上传 frontend 文件夹

1. 进入 Cloudflare Pages → "Upload assets" → 上传 `frontend/` 整个目录
2. 确保 `frontend/_redirects` 已配置正确的 tunnel URL

---

## _redirects 文件详解

```apache
# API 路由 → 转发到你的本地 tunnel
/health       https://xxx.trycloudflare.com/health       200
/macro-cycle  https://xxx.trycloudflare.com/macro-cycle  200
/simulate     https://xxx.trycloudflare.com/simulate     200
/simulate/*   https://xxx.trycloudflare.com/simulate/:splat 200
/sensitivity/* https://xxx.trycloudflare.com/sensitivity/:splat 200
/cache/*      https://xxx.trycloudflare.com/cache/:splat 200

# 静态资源 → Pages CDN 直接服务
/static/*     /static/:splat          200

# SPA 兜底
/*            /index.html              200
```

- `200` = 代理模式（不改变 URL，用户看到的是你的 Pages 域名）
- `:splat` = 通配符匹配，把子路径透传给 tunnel

---

## Cloudflare Pages Functions (替代方案)

除了 `_redirects`，你还可以使用 Pages Functions（已预置）：

`frontend/functions/_middleware.js` 会自动：
1. 识别 API 路由（/health, /simulate, /macro-cycle 等）
2. 从环境变量 `TUNNEL_URL` 读取 tunnel 地址
3. 代理请求到你的本地后端
4. 非 API 路由直接返回静态文件（CDN）

**设置环境变量：**
```
Pages Dashboard → 项目 → Settings → Environment variables
→ 添加 TUNNEL_URL = https://你的-tunnel-url.trycloudflare.com
```

---

## 配置文件对比

| 文件 | 用途 | 部署方式 |
|------|------|----------|
| `frontend/_redirects` | 静态路由配置（推荐） | 随 Pages 部署 |
| `frontend/functions/_middleware.js` | 动态路由（需要环境变量） | 随 Pages 部署 |
| `cloudflare-pages/index.html` | Tunnel 配置 UI（本地使用） | 在 localhost:8000/tunnel-config |
| `start_public.bat` | 一键启动后端+Tunnel | 本地运行 |
| `start_tunnel.bat` | 单独启动 Tunnel | 本地运行 |

---

## 注意事项

| 事项 | 说明 |
|------|------|
| **Tunnel URL 变化** | TryCloudflare 每次重启都会生成新的 URL，需要更新 `_redirects` |
| **固定域名方案** | 注册 Cloudflare 账号 → 创建命名 Tunnel → 绑定自己的域名 |
| **延迟** | API 请求需要经过 Cloudflare → 你的电脑，首次请求约 1-3 秒 |
| **并发** | 免费 tunnel 有连接数限制，适合演示和测试 |
| **数据安全** | 数据只在你本地计算，tunnel 只传输加密的 API 请求 |
| **cloudflared 安装** | 从 https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ 下载 |

---

## 手动安装 cloudflared

### Windows
```powershell
# 方法 1：使用 winget（Windows 10/11）
winget install cloudflare.cloudflared

# 方法 2：手动下载
# 下载 https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
# 重命名为 cloudflared.exe 并放入 PATH

# 方法 3：使用 pip
pip install cloudflared
# 然后找到安装位置：python -c "import cloudflared; print(cloudflared.__file__)"
```

### macOS
```bash
brew install cloudflared
```

### Linux
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/
```

---

## 文件结构

```
credit_sim/
├── main.py                      # FastAPI 后端（新增 /tunnel-config 路由）
├── start_public.bat             # 【重构】一键启动后端 + Tunnel
├── start_tunnel.bat             # 【新增】单独启动 Tunnel
├── frontend/
│   ├── final.html               # 主仪表盘（ECharts）
│   ├── _redirects               # 【新增】Cloudflare Pages 路由配置
│   └── functions/
│       └── _middleware.js       # 【更新】API 代理中间件
├── cloudflare-pages/
│   └── index.html               # 【新增】Tunnel 配置 UI
└── CLOUDFLARE_DEPLOY.md         # 【更新】本文档