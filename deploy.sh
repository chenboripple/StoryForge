#!/bin/bash
set -e

# StoryForge 自动部署脚本
# 配置来自 ~/.storyforge/storyforge.yaml

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
DEPLOY_DIR="$PROJECT_ROOT/.deploy"
PID_FILE="$DEPLOY_DIR/server.pid"
USER_CONFIG_DIR="$HOME/.storyforge"
LOG_DIR="$USER_CONFIG_DIR/logs"
LOG_RETENTION_DAYS=15
MAX_WORKERS=10
GUNICORN_LOG_CONFIG="$DEPLOY_DIR/gunicorn_logging.conf"
CONFIG_FILE="$USER_CONFIG_DIR/storyforge.yaml"
CONFIG_EXAMPLE_MD="$PROJECT_ROOT/docs/config-example.md"
LAUNCHD_LABEL="com.storyforge.webconsole"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"

# 默认端口（仅当读不到配置时使用）
DEFAULT_PORT=5089
DEFAULT_HOST="0.0.0.0"

RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
RESET="\033[0m"

log_info() { echo -e "${BLUE}[INFO]${RESET} $1"; }
log_ok() { echo -e "${GREEN}[OK]${RESET} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${RESET} $1"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $1"; }

is_launchd_loaded() {
    launchctl list | grep -q "$LAUNCHD_LABEL" 2>/dev/null
}

cleanup_stale_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            log_info "已清理失效 PID 文件: $PID_FILE"
        fi
    fi
}

stop_pid_file_process() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# 从 docs/config-example.md 提取 YAML 代码块
_extract_example_yaml() {
    if [ -f "$CONFIG_EXAMPLE_MD" ]; then
        python3 - <<PYEOF
import re
with open("$CONFIG_EXAMPLE_MD", "r", encoding="utf-8") as f:
    content = f.read()
# 查找第一个 ```yaml ... ``` 代码块
match = re.search(r"```yaml\n(.*?)\n```", content, re.DOTALL)
if match:
    print(match.group(1))
PYEOF
    fi
}

# 从配置文件读取端口（依赖虚拟环境内的 PyYAML）
read_config() {
    local field="$1"
    local default="$2"
    local result=""

    if [ -d "$VENV_DIR" ]; then
        result=$("$VENV_DIR/bin/python" - <<PYEOF 2>/dev/null || true
import sys
sys.path.insert(0, "$PROJECT_ROOT")
try:
    from core.config import get_config
    cfg = get_config()
    print(getattr(cfg.server, "$field"))
except Exception:
    pass
PYEOF
)
    fi

    if [ -z "$result" ]; then
        echo "$default"
    else
        echo "$result"
    fi
}

resolve_worker_args() {
    local workers=$(read_config workers "")

    # 允许不配置 workers，交给 gunicorn 使用默认值；配置了则不做上限限制。
    if [ -z "$workers" ] || [ "$workers" = "None" ]; then
        echo ""
        return
    fi

    if [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
        if [ "$workers" -gt "$MAX_WORKERS" ]; then
            log_warn "server.workers=$workers 超过上限 $MAX_WORKERS，已自动调整为 $MAX_WORKERS"
            workers=$MAX_WORKERS
        fi
        echo "-w $workers"
    else
        log_warn "server.workers 配置无效: $workers，已回退为 gunicorn 默认 worker 数"
        echo ""
    fi
}

# 检查是否有正在运行的进程
is_running() {
    if [ ! -f "$PID_FILE" ]; then
        return 1
    fi
    local pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -z "$pid" ]; then
        return 1
    fi
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        rm -f "$PID_FILE"
        return 1
    fi
}

# 创建必要目录
mkdirs() {
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$USER_CONFIG_DIR"
    cleanup_old_logs
}

cleanup_old_logs() {
    # 仅清理日志目录中超过保留天数的日志文件，避免误删其他文件
    if [ ! -d "$LOG_DIR" ]; then
        return
    fi

    find "$LOG_DIR" -type f \
        \( -name "*.log" -o -name "*.log.*" \) \
        -mtime +$LOG_RETENTION_DAYS \
        -delete 2>/dev/null || true
}

generate_gunicorn_log_config() {
    cat > "$GUNICORN_LOG_CONFIG" <<EOF
[loggers]
keys=root,gunicorn.error,gunicorn.access

[handlers]
keys=error_file,access_file

[formatters]
keys=generic,access

[logger_root]
level=INFO
handlers=error_file

[logger_gunicorn.error]
level=INFO
handlers=error_file
propagate=0
qualname=gunicorn.error

[logger_gunicorn.access]
level=INFO
handlers=access_file
propagate=0
qualname=gunicorn.access

[handler_error_file]
class=logging.handlers.TimedRotatingFileHandler
level=INFO
formatter=generic
args=('${LOG_DIR}/error.log', 'midnight', 1, ${LOG_RETENTION_DAYS}, 'utf-8', False, False)

[handler_access_file]
class=logging.handlers.TimedRotatingFileHandler
level=INFO
formatter=access
args=('${LOG_DIR}/access.log', 'midnight', 1, ${LOG_RETENTION_DAYS}, 'utf-8', False, False)

[formatter_generic]
format=%(asctime)s [%(process)d] [%(levelname)s] %(message)s
datefmt=%Y-%m-%d %H:%M:%S

[formatter_access]
format=%(asctime)s %(message)s
datefmt=%Y-%m-%d %H:%M:%S
EOF
}

# 确保配置文件存在；不存在则从 docs/config-example.md 复制
ensure_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        mkdir -p "$USER_CONFIG_DIR"
        local yaml_content=$(_extract_example_yaml)
        if [ -n "$yaml_content" ]; then
            echo "$yaml_content" > "$CONFIG_FILE"
            log_warn "未找到配置文件，已从 docs/config-example.md 复制到: $CONFIG_FILE"
            log_warn "请按需编辑该文件后重新部署"
        else
            log_warn "未找到配置文件，将使用内置默认值"
        fi
    fi
}

# 安装 Python 依赖
install_python() {
    log_info "设置 Python 虚拟环境..."
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        log_ok "创建虚拟环境: $VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"
    log_info "安装 Python 依赖..."
    pip install -q --upgrade pip
    pip install -q -r "$PROJECT_ROOT/requirements.txt"
    log_ok "Python 依赖安装完成"
}

# 安装 Node 依赖并构建前端
install_build_client() {
    log_info "检查前端依赖..."
    if [ ! -d "$PROJECT_ROOT/client/node_modules" ]; then
        log_info "安装 npm 依赖..."
        cd "$PROJECT_ROOT/client"
        npm install
        cd "$PROJECT_ROOT"
        log_ok "前端依赖安装完成"
    fi

    log_info "构建前端 (生产模式)..."
    cd "$PROJECT_ROOT/client"
    npm run build
    cd "$PROJECT_ROOT"
    log_ok "前端构建完成"
}

# 启动服务
start_server() {
    if is_running; then
        log_warn "服务已经在运行 (PID: $(cat "$PID_FILE"))"
        return 0
    fi

    mkdirs
    ensure_config
    generate_gunicorn_log_config

    source "$VENV_DIR/bin/activate"

    local host=$(read_config host "$DEFAULT_HOST")
    local port=$(read_config port "$DEFAULT_PORT")
    local worker_args=$(resolve_worker_args)

    log_info "启动服务器 (host: $host, port: $port)..."
    log_info "配置文件: $CONFIG_FILE"
    if [ -n "$worker_args" ]; then
        log_info "Gunicorn workers: ${worker_args#-w }"
    else
        log_info "Gunicorn workers: 使用默认值"
    fi

    cd "$PROJECT_ROOT"
    gunicorn -k uvicorn.workers.UvicornWorker ${worker_args} -b "$host:$port" web_console.app:app \
        --pid "$PID_FILE" \
        --daemon \
        --log-config "$GUNICORN_LOG_CONFIG" \
        --access-logfile -

    sleep 2

    if is_running; then
        log_ok "服务已启动 (PID: $(cat "$PID_FILE"))"
        log_info "访问: http://localhost:$port"
    else
        log_error "服务启动失败，请查看日志: $LOG_DIR/error.log"
        return 1
    fi
}

# 停止服务
stop_server() {
    if ! is_running; then
        log_warn "服务未运行"
        return 0
    fi

    local pid=$(cat "$PID_FILE")
    log_info "停止服务 (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # 等待最多 10 秒
    for _ in {1..20}; do
        if ! is_running; then
            break
        fi
        sleep 0.5
    done

    if is_running; then
        log_warn "优雅停止超时，强制 kill -9..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

    rm -f "$PID_FILE"
    log_ok "服务已停止"
}

# 查看状态
show_status() {
    local port=$(read_config port "$DEFAULT_PORT")
    echo "========================================"
    echo "      StoryForge 部署状态"
    echo "========================================"
    echo "配置文件: $CONFIG_FILE"
    if [ -f "$CONFIG_FILE" ]; then
        log_ok "配置: 已加载"
    else
        log_warn "配置: 未找到（使用默认值）"
    fi

    if is_running; then
        log_ok "服务状态: 运行中 (PID: $(cat "$PID_FILE"))"
        if command -v lsof >/dev/null 2>&1; then
            if lsof -ti :$port >/dev/null 2>&1; then
                log_ok "端口 $port: 已占用 (正常)"
            fi
        fi
        echo "访问地址: http://localhost:$port"
        echo "访问日志: $LOG_DIR/access.log"
        echo "错误日志: $LOG_DIR/error.log"
    else
        log_warn "服务状态: 未运行"
    fi
    echo "========================================"
}

# 查看日志
show_logs() {
    if [ -z "$1" ]; then
        log_info "显示最近 50 行错误日志..."
        tail -n 50 -f "$LOG_DIR/error.log" 2>/dev/null || log_warn "日志文件不存在或为空"
    elif [ "$1" = "access" ]; then
        log_info "显示最近 50 行访问日志..."
        tail -n 50 -f "$LOG_DIR/access.log" 2>/dev/null || log_warn "日志文件不存在或为空"
    elif [ "$1" = "all" ]; then
        log_info "同时显示访问日志和错误日志..."
        tail -n 30 -f "$LOG_DIR/access.log" "$LOG_DIR/error.log" 2>/dev/null || true
    fi
}

generate_launchd_plist() {
    mkdir -p "$HOME/Library/LaunchAgents"
    mkdirs
    ensure_config

    local host=$(read_config host "$DEFAULT_HOST")
    local port=$(read_config port "$DEFAULT_PORT")
    local workers=$(read_config workers "")
    local launchd_workers=""
    generate_gunicorn_log_config

    if [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
        if [ "$workers" -gt "$MAX_WORKERS" ]; then
            log_warn "server.workers=$workers 超过上限 $MAX_WORKERS，launchd 已自动调整为 $MAX_WORKERS"
            workers=$MAX_WORKERS
        fi
        launchd_workers="$workers"
    elif [ -n "$workers" ] && [ "$workers" != "None" ]; then
        log_warn "server.workers 配置无效: $workers，launchd 将使用 gunicorn 默认 worker 数"
    fi

    cat > "$LAUNCHD_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LAUNCHD_LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$VENV_DIR/bin/gunicorn</string>
    <string>-k</string>
    <string>uvicorn.workers.UvicornWorker</string>
$(if [ -n "$launchd_workers" ]; then
    cat <<INNER
    <string>-w</string>
    <string>$launchd_workers</string>
INNER
fi)
    <string>-b</string>
    <string>$host:$port</string>
    <string>web_console.app:app</string>
    <string>--pid</string>
    <string>$PID_FILE</string>
        <string>--log-config</string>
        <string>$GUNICORN_LOG_CONFIG</string>
        <string>--access-logfile</string>
        <string>-</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$PROJECT_ROOT</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.err.log</string>
</dict>
</plist>
EOF
}

install_persistent_service() {
    mkdirs
    ensure_config
    cleanup_stale_pid
    stop_pid_file_process

    if [ ! -x "$VENV_DIR/bin/gunicorn" ]; then
        log_info "未检测到可用 gunicorn，先安装 Python 依赖..."
        install_python
    fi

    generate_launchd_plist

    launchctl stop "$LAUNCHD_LABEL" >/dev/null 2>&1 || true
    launchctl unload "$LAUNCHD_PLIST" >/dev/null 2>&1 || true
    launchctl load -w "$LAUNCHD_PLIST"

    log_ok "已安装并加载常驻服务: $LAUNCHD_LABEL"
    log_info "launchd 配置: $LAUNCHD_PLIST"
    log_info "服务将随登录自动启动，且不会因 VS Code 关闭而停止"
}

uninstall_persistent_service() {
    launchctl unload "$LAUNCHD_PLIST" >/dev/null 2>&1 || true
    rm -f "$LAUNCHD_PLIST"
    log_ok "已卸载常驻服务: $LAUNCHD_LABEL"
}

start_persistent_service() {
    if [ ! -f "$LAUNCHD_PLIST" ]; then
        log_error "未找到 launchd 配置，请先执行: ./deploy.sh service-install"
        return 1
    fi

    cleanup_stale_pid

    if ! is_launchd_loaded; then
        launchctl load -w "$LAUNCHD_PLIST"
    fi

    launchctl start "$LAUNCHD_LABEL" >/dev/null 2>&1 || true
    log_ok "常驻服务启动命令已发送"
}

stop_persistent_service() {
    launchctl stop "$LAUNCHD_LABEL" >/dev/null 2>&1 || true
    launchctl unload "$LAUNCHD_PLIST" >/dev/null 2>&1 || true
    stop_pid_file_process
    log_ok "常驻服务已停止并卸载（配置文件保留）"
}

show_service_status() {
    echo "========================================"
    echo "     StoryForge 常驻服务状态"
    echo "========================================"
    echo "服务名: $LAUNCHD_LABEL"
    echo "配置文件: $LAUNCHD_PLIST"

    if [ -f "$LAUNCHD_PLIST" ]; then
        log_ok "launchd 配置: 已存在"
    else
        log_warn "launchd 配置: 不存在"
    fi

    if is_launchd_loaded; then
        log_ok "加载状态: 已加载"
    else
        log_warn "加载状态: 未加载"
    fi

    local port=$(read_config port "$DEFAULT_PORT")
    if command -v lsof >/dev/null 2>&1 && lsof -ti :$port >/dev/null 2>&1; then
        log_ok "端口 $port: 已监听"
        echo "访问地址: http://localhost:$port"
    else
        log_warn "端口 $port: 未监听"
    fi

    echo "日志: $LOG_DIR/launchd.out.log"
    echo "日志: $LOG_DIR/launchd.err.log"
    echo "========================================"
}

# 完整部署流程
full_deploy() {
    log_info "========================================"
    log_info "      StoryForge 完整部署"
    log_info "========================================"
    mkdirs
    ensure_config

    stop_server || true

    install_python
    install_build_client
    start_server

    show_status
}

# 帮助信息
show_help() {
    cat <<EOF
StoryForge 部署脚本

配置文件: ~/.storyforge/storyforge.yaml （首次运行会自动从 docs/config-example.md 复制）

用法:
  ./deploy.sh [命令]

命令:
  install    - 只安装依赖 (Python + Node)，不启动
  build      - 安装依赖 + 构建前端，不启动
  start      - 启动服务（端口/host 来自配置文件）
  stop       - 停止服务
  restart    - 重启服务
  status     - 查看运行状态
  logs       - 查看错误日志（默认）
  logs access  - 查看访问日志
  logs all     - 查看所有日志
  config     - 查看当前配置
    service-install   - 安装并加载 macOS 常驻服务（launchd）
    service-start     - 启动 macOS 常驻服务
    service-stop      - 停止并卸载 macOS 常驻服务
    service-uninstall - 卸载 macOS 常驻服务配置
    service-status    - 查看 macOS 常驻服务状态
  deploy     - 完整部署 (install + build + restart，默认)

EOF
}

# 显示当前配置
show_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_warn "配置文件不存在: $CONFIG_FILE"
        log_info "文档位置: $CONFIG_EXAMPLE_MD"
        return
    fi

    echo "========================================"
    echo "  $CONFIG_FILE"
    echo "========================================"
    cat "$CONFIG_FILE"
    echo "========================================"
}

# 主逻辑
main() {
    cd "$PROJECT_ROOT"
    case "${1:-deploy}" in
        install)
            mkdirs
            ensure_config
            install_python
            install_build_client
            log_ok "依赖安装完成"
            ;;
        build)
            mkdirs
            install_build_client
            log_ok "前端构建完成"
            ;;
        start)
            start_server
            ;;
        stop)
            stop_server
            ;;
        restart)
            stop_server
            start_server
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        config)
            show_config
            ;;
        service-install)
            install_persistent_service
            ;;
        service-start)
            start_persistent_service
            ;;
        service-stop)
            stop_persistent_service
            ;;
        service-uninstall)
            uninstall_persistent_service
            ;;
        service-status)
            show_service_status
            ;;
        deploy)
            full_deploy
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
