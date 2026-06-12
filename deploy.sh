#!/bin/bash
# ============================================================
# 价值投资自动化选股系统 - 一键部署脚本
# 适用环境：阿里云 ECS / 主流 Linux 发行版（CentOS/Ubuntu/Debian）
# 作者：系统维护组
# 版本：v3.0
# ============================================================

set -e

# ---------- 可配置项（按需修改） ----------
PROJECT_NAME="vinvest"
INSTALL_DIR="/opt/${PROJECT_NAME}"
BACKEND_DIR="${INSTALL_DIR}/backend"
FRONTEND_DIR="${INSTALL_DIR}/frontend"
DATA_DIR="${INSTALL_DIR}/data"
LOG_DIR="${INSTALL_DIR}/logs"
CONFIG_DIR="${INSTALL_DIR}/config"

BACKEND_PORT=8000
FRONTEND_PORT=8080
UWSGI_WORKERS=4

PYTHON_VERSION="3.11"
NODE_VERSION="20"

# 数据库配置（生产环境建议改为 PostgreSQL）
DB_TYPE="sqlite"                       # sqlite | postgresql
DB_NAME="vinvest"
DB_USER="vinvest"
DB_PASS="ChangeMe_2026"
DB_HOST="127.0.0.1"
DB_PORT="5432"

# Redis 配置
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"

# 运行用户（部署脚本会自动创建）
RUN_USER="www-data"

# ---------- 日志与颜色输出 ----------
LOG_FILE="${LOG_DIR}/deploy_$(date +%Y%m%d_%H%M%S).log"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1" | tee -a "$LOG_FILE"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1" | tee -a "$LOG_FILE"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

# ---------- 前置检查 ----------
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "请使用 root 用户或 sudo 运行本脚本"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_NAME="$ID"
        OS_VERSION="$VERSION_ID"
    else
        OS_NAME="unknown"
    fi
    log_info "检测到操作系统：${OS_NAME} ${OS_VERSION}"
}

init_dirs() {
    mkdir -p "$INSTALL_DIR" "$BACKEND_DIR" "$FRONTEND_DIR" "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
    log_ok "部署目录已初始化：${INSTALL_DIR}"
}

# ---------- 系统依赖安装 ----------
install_system_deps() {
    log_info "正在安装系统基础依赖..."

    case "$OS_NAME" in
        ubuntu|debian)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -y >> "$LOG_FILE" 2>&1
            apt-get install -y curl wget git build-essential \
                python3 python3-pip python3-venv python3-dev \
                nginx redis-server postgresql postgresql-contrib \
                libpq-dev >> "$LOG_FILE" 2>&1
            systemctl enable redis-server postgresql nginx >> "$LOG_FILE" 2>&1 || true
            systemctl start redis-server postgresql >> "$LOG_FILE" 2>&1 || true
            ;;
        centos|rhel|rocky|alma)
            yum install -y epel-release >> "$LOG_FILE" 2>&1 || true
            yum install -y curl wget git gcc gcc-c++ make \
                python3 python3-pip python3-devel \
                nginx redis postgresql-server postgresql-devel \
                postgresql-contrib >> "$LOG_FILE" 2>&1
            systemctl enable redis postgresql nginx >> "$LOG_FILE" 2>&1 || true
            # 初始化 PostgreSQL（CentOS 首次需要）
            if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then
                postgresql-setup --initdb >> "$LOG_FILE" 2>&1 || true
            fi
            systemctl start redis postgresql >> "$LOG_FILE" 2>&1 || true
            ;;
        *)
            log_warn "未识别的 Linux 发行版，请手动安装依赖：Python3、Git、Nginx、Redis、PostgreSQL"
            ;;
    esac
    log_ok "系统基础依赖已安装"
}

# ---------- 部署代码 ----------
deploy_code() {
    log_info "正在部署项目代码..."

    if [ -d "$BACKEND_DIR/.git" ] || [ -f "$BACKEND_DIR/requirements.txt" ]; then
        log_info "检测到已存在部署，执行更新流程..."
        # 备份旧版本
        BACKUP_DIR="${INSTALL_DIR}/backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        [ -d "$BACKEND_DIR/app" ] && cp -a "$BACKEND_DIR/app" "$BACKUP_DIR/backend_app"
        [ -f "$BACKEND_DIR/.env" ] && cp "$BACKEND_DIR/.env" "$BACKUP_DIR/"
        [ -d "$CONFIG_DIR" ] && cp -a "$CONFIG_DIR" "$BACKUP_DIR/config"
        log_info "旧版本已备份至：${BACKUP_DIR}"
    fi

    # 获取当前脚本所在目录作为源码目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SOURCE_DIR="$SCRIPT_DIR"

    if [ ! -f "${SOURCE_DIR}/backend/requirements.txt" ]; then
        log_error "源码目录中未找到 backend/requirements.txt，请确认脚本位于项目根目录"
        log_error "当前源码目录：${SOURCE_DIR}"
        exit 1
    fi

    # 复制代码（保留 .env 与配置文件）
    rsync -a --delete \
        --exclude '__pycache__' --exclude '*.pyc' \
        --exclude '.venv' --exclude 'node_modules' \
        --exclude 'dist' --exclude '.git' \
        "${SOURCE_DIR}/backend/"  "$BACKEND_DIR/"
    rsync -a --delete \
        --exclude 'node_modules' --exclude 'dist' \
        --exclude '.git' \
        "${SOURCE_DIR}/frontend/" "$FRONTEND_DIR/"
    rsync -a \
        "${SOURCE_DIR}/config/"   "$CONFIG_DIR/"
    rsync -a \
        "${SOURCE_DIR}/data/"     "$DATA_DIR/"

    chown -R "$RUN_USER:$RUN_USER" "$INSTALL_DIR" 2>/dev/null || chown -R root:root "$INSTALL_DIR"
    log_ok "项目代码已部署"
}

# ---------- 后端部署 ----------
deploy_backend() {
    log_info "正在部署后端服务 (FastAPI + Uvicorn)..."

    # 创建虚拟环境
    if [ ! -d "$BACKEND_DIR/.venv" ]; then
        python3 -m venv "$BACKEND_DIR/.venv" >> "$LOG_FILE" 2>&1
    fi
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"

    # 升级 pip 与安装依赖
    pip install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1
    pip install -r "$BACKEND_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
    pip install gunicorn uvicorn[standard] >> "$LOG_FILE" 2>&1
    log_ok "Python 虚拟环境与依赖已就绪"

    # 生成 .env 文件
    if [ "$DB_TYPE" = "postgresql" ]; then
        DB_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    else
        DB_URL="sqlite:///${DATA_DIR}/${DB_NAME}.db"
    fi

    cat > "$BACKEND_DIR/.env" <<EOF
# 生产环境变量配置
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
DATABASE_URL=${DB_URL}
EOF
    chmod 640 "$BACKEND_DIR/.env"

    # 同步生成 YAML 配置（覆盖 default_config.yaml 中的关键项）
    cat > "$CONFIG_DIR/default_config.yaml" <<EOF
# 生产环境基础设施配置
database:
  url: "${DB_URL}"

redis:
  host: ${REDIS_HOST}
  port: ${REDIS_PORT}

knowledge:
  vector_db_path: "${DATA_DIR}/chroma_db"
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2"

output:
  report_dir: "${DATA_DIR}/reports"
EOF

    mkdir -p "$DATA_DIR/chroma_db" "$DATA_DIR/reports"

    # 数据库初始化（SQLite 自动建库，PostgreSQL 需手动建立数据库）
    if [ "$DB_TYPE" = "postgresql" ]; then
        log_info "正在初始化 PostgreSQL 数据库..."
        su - postgres -c "psql -c \"CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';\"" 2>/dev/null || true
        su - postgres -c "psql -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};\"" 2>/dev/null || true
        su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};\"" 2>/dev/null || true
        if [ -f "$DATA_DIR/init.sql" ]; then
            su - postgres -c "psql -d ${DB_NAME} -f $DATA_DIR/init.sql" >> "$LOG_FILE" 2>&1 || true
        fi
        log_ok "PostgreSQL 初始化完成"
    else
        touch "${DATA_DIR}/${DB_NAME}.db"
        log_ok "SQLite 数据库已就绪"
    fi

    # 修改 main.py 的 CORS 与监听地址（保留原文件不动，使用环境变量控制）
    # 通过 systemd 服务传入监听参数

    # 安装 systemd 服务
    cat > /etc/systemd/system/${PROJECT_NAME}-backend.service <<EOF
[Unit]
Description=Value Investing Backend (FastAPI)
After=network.target redis-server.service postgresql.service

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${BACKEND_DIR}
Environment="PATH=${BACKEND_DIR}/.venv/bin"
Environment="VINVEST_CONFIG=${CONFIG_DIR}/default_config.yaml"
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port ${BACKEND_PORT} \
    --workers ${UWSGI_WORKERS} --log-level info \
    --access-log --proxy-headers
Restart=on-failure
RestartSec=5
StandardOutput=append:${LOG_DIR}/backend.log
StandardError=append:${LOG_DIR}/backend_error.log

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${PROJECT_NAME}-backend" >> "$LOG_FILE" 2>&1
    systemctl restart "${PROJECT_NAME}-backend"
    sleep 3
    if systemctl is-active --quiet "${PROJECT_NAME}-backend"; then
        log_ok "后端服务已启动（http://127.0.0.1:${BACKEND_PORT}）"
    else
        log_error "后端服务启动失败，请查看日志：${LOG_DIR}/backend.log"
        exit 1
    fi
}

# ---------- 前端部署 ----------
deploy_frontend() {
    log_info "正在部署前端 (Vue3 + Vite)..."

    # 安装 Node.js（如未安装）
    if ! command -v node >/dev/null 2>&1; then
        log_info "正在安装 Node.js ${NODE_VERSION}..."
        curl -fsSL https://rpm.nodesource.com/setup_${NODE_VERSION}.x | bash - >> "$LOG_FILE" 2>&1 \
            || curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - >> "$LOG_FILE" 2>&1
        case "$OS_NAME" in
            ubuntu|debian) apt-get install -y nodejs >> "$LOG_FILE" 2>&1 ;;
            centos|rhel|rocky|alma) yum install -y nodejs >> "$LOG_FILE" 2>&1 ;;
        esac
    fi

    node -v >> "$LOG_FILE" 2>&1
    npm -v  >> "$LOG_FILE" 2>&1

    # 使用国内镜像加速（阿里云 ECS 用户建议开启）
    npm config set registry https://registry.npmmirror.com >> "$LOG_FILE" 2>&1 || true

    cd "$FRONTEND_DIR"
    npm install >> "$LOG_FILE" 2>&1

    # 修改 Vite 代理配置（指向前端 /api 路径 -> 后端 8000）
    # 已在 Nginx 层完成反向代理，此处仅构建静态资源
    npm run build >> "$LOG_FILE" 2>&1
    log_ok "前端资源已构建：${FRONTEND_DIR}/dist"

    # 安装 Nginx 配置
    cat > /etc/nginx/conf.d/${PROJECT_NAME}.conf <<EOF
server {
    listen       ${FRONTEND_PORT};
    server_name  _;
    client_max_body_size 20M;

    # 前端静态资源
    location / {
        root   ${FRONTEND_DIR}/dist;
        index  index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # API 反向代理至后端 FastAPI
    location /api/ {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }

    # 健康检查
    location /health {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT}/health;
    }

    # 日志
    access_log  ${LOG_DIR}/nginx_access.log;
    error_log   ${LOG_DIR}/nginx_error.log warn;
}
EOF

    # 测试并重启 Nginx
    if ! nginx -t >> "$LOG_FILE" 2>&1; then
        log_error "Nginx 配置语法错误，请查看日志"
        exit 1
    fi

    systemctl enable nginx >> "$LOG_FILE" 2>&1 || true
    systemctl restart nginx
    log_ok "前端 Nginx 服务已启动（http://0.0.0.0:${FRONTEND_PORT}）"
}

# ---------- 防火墙与安全 ----------
configure_firewall() {
    log_info "正在配置防火墙..."
    case "$OS_NAME" in
        ubuntu|debian)
            ufw allow ${FRONTEND_PORT}/tcp >> "$LOG_FILE" 2>&1 || true
            ufw reload >> "$LOG_FILE" 2>&1 || true
            ;;
        centos|rhel|rocky|alma)
            firewall-cmd --permanent --add-port=${FRONTEND_PORT}/tcp >> "$LOG_FILE" 2>&1 || true
            firewall-cmd --reload >> "$LOG_FILE" 2>&1 || true
            ;;
    esac
    # 仅放行前端端口，后端通过 127.0.0.1 本地通信，不对外暴露
    log_ok "防火墙已放行前端端口 ${FRONTEND_PORT}"
}

# ---------- 健康检查 ----------
health_check() {
    log_info "正在进行健康检查..."
    sleep 2
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" || echo "000")
    if [ "$code" = "200" ]; then
        log_ok "后端健康检查通过 (HTTP 200)"
    else
        log_warn "后端健康检查返回 ${code}，请查看日志"
    fi

    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}/" || echo "000")
    if [ "$code" = "200" ]; then
        log_ok "前端健康检查通过 (HTTP 200)"
    else
        log_warn "前端健康检查返回 ${code}，请查看日志"
    fi
}

# ---------- 输出总结 ----------
print_summary() {
    local pub_ip
    pub_ip=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

    echo ""
    echo "============================================================"
    echo -e "${GREEN}✅ 部署完成！${NC}"
    echo "============================================================"
    echo "  前端访问地址：http://${pub_ip}:${FRONTEND_PORT}"
    echo "  后端 API    ：http://127.0.0.1:${BACKEND_PORT}"
    echo "  健康检查    ：curl http://127.0.0.1:${BACKEND_PORT}/health"
    echo ""
    echo "  常用命令："
    echo "    systemctl status ${PROJECT_NAME}-backend    # 查看后端状态"
    echo "    systemctl status nginx                      # 查看 Nginx 状态"
    echo "    journalctl -u ${PROJECT_NAME}-backend -f    # 实时查看后端日志"
    echo "    tail -f ${LOG_DIR}/backend.log              # 后端运行日志"
    echo "    tail -f ${LOG_DIR}/nginx_access.log         # Nginx 访问日志"
    echo ""
    echo "  配置文件："
    echo "    后端环境变量：${BACKEND_DIR}/.env"
    echo "    基础设施配置：${CONFIG_DIR}/default_config.yaml"
    echo "    Nginx 配置  ：/etc/nginx/conf.d/${PROJECT_NAME}.conf"
    echo "============================================================"
    echo ""
    echo -e "${YELLOW}⚠️  安全提醒：请务必修改以下默认密码（在 deploy.sh 顶部可配置）：${NC}"
    echo "   - 数据库密码：DB_PASS"
    echo "   - 如需暴露到公网，建议配置 HTTPS（Let's Encrypt）与 阿里云安全组"
    echo ""
}

# ---------- 主流程 ----------
main() {
    check_root
    detect_os
    init_dirs
    mkdir -p "$LOG_DIR"
    log_info "部署日志文件：${LOG_FILE}"
    log_info "开始时间：$(date '+%Y-%m-%d %H:%M:%S')"

    install_system_deps
    deploy_code
    deploy_backend
    deploy_frontend
    configure_firewall
    health_check
    print_summary

    log_info "结束时间：$(date '+%Y-%m-%d %H:%M:%S')"
}

main "$@"
