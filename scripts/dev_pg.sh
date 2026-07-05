#!/usr/bin/env bash
# ==========================================================================
# scripts/dev_pg.sh — 本機/沙盒 PostgreSQL 16 一鍵初始化腳本（WP1 基盤）
# ==========================================================================
# 用途：讓 Schema B 的 integration 測試（tests_integration/）有一個可重複、
#       冪等建立的本機 PostgreSQL 環境可以連線。
#
# 這個腳本會依序做：
#   1. 確認 PostgreSQL 16 的 cluster「main」存在；不存在就用 pg_createcluster 建立。
#   2. 啟動 cluster（若已啟動則略過）。
#   3. 建立資料庫使用者 voc（密碼 voc，僅供本機開發測試用，非正式帳密）。
#   4. 建立資料庫 voc_b（owner=voc）。
#   5. 用 psql 做一次連線驗證，印出成功訊息。
#
# 冪等性：所有步驟都先檢查「是否已存在/已啟動」才動作，可重複執行不會報錯。
#
# 前置需求：沙盒/本機已安裝 PostgreSQL 16 binaries（apt install postgresql-16），
#           且本腳本以具備 pg_ctlcluster / sudo -u postgres 權限的使用者執行
#           （沙盒環境為 root，可直接 sudo -u postgres）。
#
# 連線字串（供 config.py VOC_B_DB_URL 使用）：
#   postgresql+psycopg2://voc:voc@localhost/voc_b
#
# 使用方式：
#   bash scripts/dev_pg.sh
# ==========================================================================
set -euo pipefail

PG_VERSION="16"
PG_CLUSTER="main"
DB_USER="voc"
DB_PASS="voc"       # 本機開發測試用簡單密碼，非正式環境密碼
DB_NAME="voc_b"

echo "[dev_pg] 步驟 1/5：確認 PostgreSQL ${PG_VERSION} cluster「${PG_CLUSTER}」是否存在..."
if ! pg_lsclusters --no-header 2>/dev/null | awk '{print $1, $2}' | grep -qx "${PG_VERSION} ${PG_CLUSTER}"; then
    echo "[dev_pg] 找不到 cluster，執行 pg_createcluster ${PG_VERSION} ${PG_CLUSTER} ..."
    pg_createcluster "${PG_VERSION}" "${PG_CLUSTER}"
else
    echo "[dev_pg] cluster 已存在，略過建立。"
fi

echo "[dev_pg] 步驟 2/5：確認 cluster 是否已啟動..."
CLUSTER_STATUS=$(pg_lsclusters --no-header 2>/dev/null | awk -v v="${PG_VERSION}" -v c="${PG_CLUSTER}" '$1==v && $2==c {print $4}')
if [ "${CLUSTER_STATUS}" != "online" ]; then
    echo "[dev_pg] cluster 未啟動，執行 pg_ctlcluster ${PG_VERSION} ${PG_CLUSTER} start ..."
    pg_ctlcluster "${PG_VERSION}" "${PG_CLUSTER}" start
    # 等待 cluster 真正接受連線（最多等 15 秒）
    for i in $(seq 1 15); do
        if sudo -u postgres pg_isready -q; then
            break
        fi
        sleep 1
    done
else
    echo "[dev_pg] cluster 已在線，略過啟動。"
fi

echo "[dev_pg] 步驟 3/5：確認使用者 ${DB_USER} 是否存在..."
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
    ELSE
        ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';
    END IF;
END
\$\$;
"

echo "[dev_pg] 步驟 4/5：確認資料庫 ${DB_NAME} 是否存在..."
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'")
if [ "${DB_EXISTS}" != "1" ]; then
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
else
    echo "[dev_pg] 資料庫已存在，略過建立。"
fi

echo "[dev_pg] 步驟 5/5：驗證連線..."
PGPASSWORD="${DB_PASS}" psql -h localhost -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT current_database(), current_user, version();"

echo ""
echo "[dev_pg] 完成！連線字串（供 .env 的 VOC_B_DB_URL 使用）："
echo "  postgresql+psycopg2://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}"
