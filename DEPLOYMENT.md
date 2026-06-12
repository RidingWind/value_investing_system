# 价值投资自动化选股系统 - ECS 部署手册

**版本**：v3.0  
**适用系统**：阿里云 ECS / Ubuntu 20.04+ / CentOS 7+ / Rocky Linux 8+  
**架构**：前端 Vue3（Vite 构建）+ 后端 FastAPI（Python 3.11）+ Redis + SQLite/PostgreSQL + Nginx 反向代理

---

## 目录

1. [一、服务器资源与前置准备](#一服务器资源与前置准备)
2. [二、一键部署脚本使用](#二一键部署脚本使用)
3. [三、目录结构说明](#三目录结构说明)
4. [四、配置文件详解](#四配置文件详解)
5. [五、服务管理与维护](#五服务管理与维护)
6. [六、从旧版本升级](#六从旧版本升级)
7. [七、HTTPS / 域名 / 安全加固](#七https--域名--安全加固)
8. [八、常见问题排查（FAQ）](#八常见问题排查faq)
9. [九、附录：手动部署全流程](#九附录手动部署全流程)

---

## 一、服务器资源与前置准备

### 1.1 推荐规格（阿里云 ECS）

| 环境     | vCPU | 内存  | 系统盘      | 带宽  | 操作系统推荐           |
| -------- | ---- | ----- | ----------- | ----- | ---------------------- |
| 开发/测试 | 2    | 4 GB  | 40 GB SSD   | 1 Mbps | Ubuntu 22.04 LTS 64位 |
| 生产     | 4    | 8 GB+ | 80 GB SSD+  | 5 Mbps+ | Ubuntu 22.04 LTS 64位 |

> 如使用 PostgreSQL，建议内存 ≥ 8 GB；若开启 ChromaDB 向量检索，建议 CPU ≥ 4 核。

### 1.2 安全组配置（阿里云控制台）

在 **ECS → 安全组 → 配置规则** 中放行以下入方向端口：

| 协议 | 端口范围 | 授权对象   | 说明                         |
| ---- | -------- | ---------- | ---------------------------- |
| TCP  | 22       | 你的办公IP | SSH 远程登录（建议限制来源） |
| TCP  | 8080     | 0.0.0.0/0  | 前端 HTTP 访问               |
| TCP  | 80 / 443 | 0.0.0.0/0  | 绑定域名后，开启 HTTP/HTTPS  |

**后端 8000 端口** 只在 `127.0.0.1` 本地监听，**不对外暴露**。

### 1.3 上传源码到服务器

方式一：SCP / SFTP 上传（推荐 Windows 使用 WinSCP / MobaXterm，macOS 使用 `scp`）

```bash
# 在本地终端执行（将整个项目目录上传）
scp -r /path/to/vinvest root@<ECS公网IP>:/root/
```

方式二：Git 克隆（推荐生产环境，便于升级）

```bash
# 在 ECS 上执行
apt install -y git          # Ubuntu
yum install -y git          # CentOS
git clone <你的仓库地址> /root/vinvest
```

---

## 二、一键部署脚本使用

项目根目录提供了 **`deploy.sh`**，可自动完成：安装依赖 → 部署代码 → 配置服务 → 启动并健康检查。

### 2.1 快速开始（3 步）

```bash
# 1. 进入项目根目录（包含 deploy.sh 的目录）
cd /root/vinvest

# 2. （可选）编辑脚本顶部配置（端口、数据库密码等）
vim deploy.sh

# 3. 执行一键部署
chmod +x deploy.sh
sudo ./deploy.sh
```

部署完成后将看到：

```
============================================================
✅ 部署完成！
============================================================
  前端访问地址：http://<ECS公网IP>:8080
  后端 API    ：http://127.0.0.1:8000
  健康检查    ：curl http://127.0.0.1:8000/health
```

### 2.2 脚本顶部可配置项

| 变量           | 默认值          | 说明                               |
| -------------- | --------------- | ---------------------------------- |
| `INSTALL_DIR`  | `/opt/vinvest`  | 项目安装根目录                     |
| `BACKEND_PORT` | `8000`          | 后端监听端口（本地）               |
| `FRONTEND_PORT`| `8080`          | 前端 Nginx 监听端口（对外）        |
| `UWSGI_WORKERS`| `4`             | 后端 worker 进程数（建议 = CPU核数）|
| `DB_TYPE`      | `sqlite`        | 数据库类型：`sqlite` 或 `postgresql`|
| `DB_PASS`      | `ChangeMe_2026` | **生产环境必须修改**               |
| `RUN_USER`     | `www-data`      | 运行服务的系统用户                 |

---

## 三、目录结构说明

部署完成后，服务器上目录结构为：

```
/opt/vinvest/
├── backend/                  # 后端代码（FastAPI）
│   ├── app/                  #   核心业务（api/core/services...）
│   ├── .venv/                #   Python 虚拟环境
│   ├── .env                  #   环境变量（数据库/Redis 地址）
│   └── requirements.txt
├── frontend/                 # 前端代码
│   ├── src/
│   └── dist/                 #   Vite 构建产物（Nginx 根目录）
├── config/
│   └── default_config.yaml   # 生产环境基础设施配置
├── data/
│   ├── vinvest.db            #   SQLite 数据库（如使用 sqlite）
│   ├── chroma_db/            #   向量库持久化目录
│   └── reports/              #   报表输出目录
└── logs/
    ├── deploy_YYYYMMDD.log   # 部署脚本日志
    ├── backend.log           # 后端运行日志
    ├── backend_error.log     # 后端错误日志
    ├── nginx_access.log      # Nginx 访问日志
    └── nginx_error.log       # Nginx 错误日志

/etc/systemd/system/vinvest-backend.service  # 后端服务单元
/etc/nginx/conf.d/vinvest.conf               # Nginx 站点配置
```

独立配置模板位于项目 `deploy/` 目录（脚本内部同样会生成等价内容）：

```
deploy/
├── vinvest-backend.service   # systemd 服务模板
├── vinvest.conf              # Nginx 配置模板
├── default_config.yaml       # 基础设施配置模板
└── .env.example              # 环境变量示例
```

---

## 四、配置文件详解

### 4.1 后端环境变量 `/opt/vinvest/backend/.env`

```env
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
DATABASE_URL=sqlite:////opt/vinvest/data/vinvest.db
# 或使用 PostgreSQL：
# DATABASE_URL=postgresql://vinvest:your_pass@127.0.0.1:5432/vinvest
```

> 修改后执行：`systemctl restart vinvest-backend`

### 4.2 基础设施配置 `/opt/vinvest/config/default_config.yaml`

```yaml
database:
  url: "sqlite:////opt/vinvest/data/vinvest.db"
redis:
  host: 127.0.0.1
  port: 6379
knowledge:
  vector_db_path: "/opt/vinvest/data/chroma_db"
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2"
output:
  report_dir: "/opt/vinvest/data/reports"
```

### 4.3 切换到 PostgreSQL（推荐生产环境）

1. 停止后端：`systemctl stop vinvest-backend`
2. 修改 `backend/.env` 与 `config/default_config.yaml` 中的 `DATABASE_URL`
3. 在 PostgreSQL 中建立数据库与用户：

```bash
su - postgres
psql -c "CREATE USER vinvest WITH PASSWORD '你的强密码';"
psql -c "CREATE DATABASE vinvest OWNER vinvest;"
psql -c "GRANT ALL PRIVILEGES ON DATABASE vinvest TO vinvest;"
# 如有初始化 SQL：
psql -d vinvest -f /opt/vinvest/data/init.sql
exit

systemctl start vinvest-backend
```

4. 修改 PostgreSQL `pg_hba.conf`（`/var/lib/pgsql/data/` 或 `/etc/postgresql/*/main/`），确保本地可通过密码登录。

---

## 五、服务管理与维护

### 5.1 常用 systemctl 命令

```bash
# 后端服务
systemctl status  vinvest-backend    # 查看运行状态
systemctl start   vinvest-backend
systemctl stop    vinvest-backend
systemctl restart vinvest-backend
systemctl enable  vinvest-backend    # 开机自启
systemctl disable vinvest-backend

# 查看后端实时日志
journalctl -u vinvest-backend -f
# 或查看文件日志
tail -f /opt/vinvest/logs/backend.log
tail -f /opt/vinvest/logs/backend_error.log

# Nginx 服务
systemctl status nginx
systemctl reload nginx     # 平滑重启，不中断用户（推荐修改配置后使用）
systemctl restart nginx
nginx -t                   # 测试配置文件（必须在 reload 前执行）
```

### 5.2 健康检查

```bash
# 后端健康检查
curl -s http://127.0.0.1:8000/health
# 预期输出：{"status":"ok"}

# 前端页面检查（应返回 HTTP 200）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
```

### 5.3 日志轮转

建议启用 `logrotate`，避免日志文件无限增长。创建 `/etc/logrotate.d/vinvest`：

```
/opt/vinvest/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    size 100M
}
```

执行 `logrotate -f /etc/logrotate.d/vinvest` 立即生效一次。

---

## 六、从旧版本升级

场景：已有部署 `v2.0`，现在升级到 `v3.0`。

**推荐使用 `deploy.sh` 自动升级**（脚本会自动备份旧代码与配置）：

```bash
cd /root/vinvest              # 新代码所在目录
git pull                      # 如使用 Git
sudo ./deploy.sh
```

脚本升级流程：

1. 将旧版 `backend/app`、`.env`、`config/` 备份到 `backup_<时间戳>/`
2. 覆盖代码与依赖（保留 `.venv`、`node_modules` 以加速）
3. 重启后端、重建前端静态资源、重载 Nginx
4. 执行健康检查

**如需手动回滚**：

```bash
# 假设备份目录为 /opt/vinvest/backup_20260612_110000
cp -a /opt/vinvest/backup_20260612_110000/backend_app/* /opt/vinvest/backend/app/
cp -a /opt/vinvest/backup_20260612_110000/.env           /opt/vinvest/backend/
cp -a /opt/vinvest/backup_20260612_110000/config/*       /opt/vinvest/config/
systemctl restart vinvest-backend
```

---

## 七、HTTPS / 域名 / 安全加固

### 7.1 绑定域名

1. 在域名服务商处将 `A 记录` 指向 ECS 公网 IP，例如：
   - `vinvest.example.com` → `123.45.67.89`
2. 修改 `/etc/nginx/conf.d/vinvest.conf` 中 `server_name` 为你的域名，并将监听端口改为 `80`。
3. `nginx -t && systemctl reload nginx`

### 7.2 配置免费 SSL（Let's Encrypt）

以 Ubuntu 为例：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d vinvest.example.com
# 按提示输入邮箱、同意协议，选择 "2: Redirect" 强制 HTTPS
```

证书将自动续期（Certbot 已配置 systemd timer）。

### 7.3 安全加固清单

| 项目                 | 建议操作                                                                 |
| -------------------- | ------------------------------------------------------------------------ |
| SSH 安全             | 禁用 root 密码登录，改为密钥登录；修改默认端口 22 → 其他端口            |
| 数据库密码           | 务必修改 `deploy.sh` 顶部 `DB_PASS` 默认值                              |
| 文件权限             | `/opt/vinvest/backend/.env` 已设置 `chmod 640`，其他配置同理            |
| 阿里云安全组         | 仅开放 22/80/443/8080，其他端口默认拒绝                                  |
| 数据备份             | 对 SQLite：`cp /opt/vinvest/data/vinvest.db /backup/$(date +%F).db` 每日执行 |
| 对 PostgreSQL        | `pg_dump vinvest > /backup/vinvest_$(date +%F).sql`                      |
| 定时数据采集任务     | 通过后端 `APScheduler`（已内置在 `app/core/` 中）自动执行，无需额外 cron |

---

## 八、常见问题排查（FAQ）

### Q1. 部署脚本提示 `command not found: rsync`
安装 `rsync` 即可：
```bash
apt install -y rsync     # Ubuntu
yum install -y rsync     # CentOS
```

### Q2. 后端启动失败，日志报 `ModuleNotFoundError`
进入虚拟环境手动安装缺失依赖：
```bash
source /opt/vinvest/backend/.venv/bin/activate
pip install -r /opt/vinvest/backend/requirements.txt
systemctl restart vinvest-backend
```

### Q3. 后端报 `Redis ConnectionError`
检查 Redis 是否正常启动：
```bash
systemctl status redis-server    # Ubuntu
systemctl status redis           # CentOS
redis-cli ping                   # 应返回 PONG
```

### Q4. 前端页面正常但 API 返回 502
- 检查后端是否运行：`systemctl status vinvest-backend`
- 本地 curl 验证：`curl http://127.0.0.1:8000/health`
- 查看 Nginx 错误日志：`tail /opt/vinvest/logs/nginx_error.log`
- 常见原因：后端未启动、端口被占用、`proxy_pass` 地址写错

### Q5. 前端页面空白（404）
- 确认 `npm run build` 已生成 `dist/` 目录：`ls /opt/vinvest/frontend/dist/`
- 确认 Nginx `root` 配置正确指向 dist
- `nginx -t` 验证配置语法

### Q6. PostgreSQL 报 `peer authentication failed`
编辑 `pg_hba.conf`，将本地认证方式改为 `md5`，然后 `systemctl restart postgresql`。

### Q7. ChromaDB / sentence-transformers 首次启动慢
首次加载模型会下载约 100MB 权重文件，属正常现象，生产环境可预先将模型放入 `/opt/vinvest/data/chroma_db/`。

### Q8. 端口被占用（"Address already in use"）
```bash
lsof -i :8000   # 查占用后端端口的进程
lsof -i :8080   # 查占用前端端口的进程
# 杀掉占用进程后重启服务
kill -9 <PID>
systemctl restart vinvest-backend nginx
```

---

## 九、附录：手动部署全流程

若希望完全手工部署，可按以下步骤操作（等价于 `deploy.sh`）：

### 9.1 安装系统依赖

```bash
# Ubuntu 22.04
apt update -y
apt install -y curl wget git build-essential \
    python3 python3-pip python3-venv python3-dev \
    nginx redis-server postgresql postgresql-contrib libpq-dev

systemctl enable --now redis-server postgresql nginx
```

### 9.2 创建目录与部署代码

```bash
mkdir -p /opt/vinvest/{backend,frontend,config,data,logs}
cd /opt/vinvest
rsync -a --exclude='.venv' --exclude='node_modules' --exclude='dist' --exclude='.git' \
    /root/vinvest/backend/  /opt/vinvest/backend/
rsync -a --exclude='node_modules' --exclude='dist' --exclude='.git' \
    /root/vinvest/frontend/ /opt/vinvest/frontend/
rsync -a /root/vinvest/config/ /opt/vinvest/config/
rsync -a /root/vinvest/data/   /opt/vinvest/data/
```

### 9.3 后端

```bash
cd /opt/vinvest/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn[standard]

# 写入 .env 与 default_config.yaml（参考 deploy/ 目录模板）
# ...

# 安装 systemd 服务
cp /root/vinvest/deploy/vinvest-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vinvest-backend
```

### 9.4 前端

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
cd /opt/vinvest/frontend
npm config set registry https://registry.npmmirror.com
npm install
npm run build

cp /root/vinvest/deploy/vinvest.conf /etc/nginx/conf.d/
nginx -t
systemctl restart nginx
```

### 9.5 健康检查（同前面 5.2 节）

```bash
curl http://127.0.0.1:8000/health
curl -I   http://127.0.0.1:8080/
```

---

**维护者**：系统运维组  
**最后更新**：2026-06-12  
如发现问题请提交 Issue 或联系运维邮箱。
