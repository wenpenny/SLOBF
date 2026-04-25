#!/bin/bash
# Download benchmark datasets for SLOBF

set -e

# Base directory for datasets
DATASETS_DIR="datasets/raw"
mkdir -p "$DATASETS_DIR"

# Coreutils
COREUTILS_VER="9.1"
COREUTILS_URL="https://ftp.gnu.org/gnu/coreutils/coreutils-$COREUTILS_VER.tar.xz"
if [ ! -d "$DATASETS_DIR/coreutils-$COREUTILS_VER" ]; then
    echo "Downloading Coreutils $COREUTILS_VER..."
    wget -c "$COREUTILS_URL" -P "$DATASETS_DIR"
    tar -xf "$DATASETS_DIR/coreutils-$COREUTILS_VER.tar.xz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/coreutils-$COREUTILS_VER" "$DATASETS_DIR/coreutils"
else
    echo "Coreutils already exists."
fi

# SQLite
SQLITE_VER="3450300" # 3.45.3
SQLITE_URL="https://www.sqlite.org/2024/sqlite-src-$SQLITE_VER.zip"
if [ ! -d "$DATASETS_DIR/sqlite" ]; then
    echo "Downloading SQLite..."
    wget -c "$SQLITE_URL" -P "$DATASETS_DIR"
    unzip -q "$DATASETS_DIR/sqlite-src-$SQLITE_VER.zip" -d "$DATASETS_DIR"
    mv "$DATASETS_DIR/sqlite-src-$SQLITE_VER" "$DATASETS_DIR/sqlite"
else
    echo "SQLite already exists."
fi

# zlib
ZLIB_VER="1.3.1"
ZLIB_URL="https://github.com/madler/zlib/archive/refs/tags/v$ZLIB_VER.tar.gz"
if [ ! -d "$DATASETS_DIR/zlib" ]; then
    echo "Downloading zlib..."
    wget -c "$ZLIB_URL" -P "$DATASETS_DIR" -O "$DATASETS_DIR/zlib-$ZLIB_VER.tar.gz"
    tar -xf "$DATASETS_DIR/zlib-$ZLIB_VER.tar.gz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/zlib-$ZLIB_VER" "$DATASETS_DIR/zlib"
else
    echo "zlib already exists."
fi

echo "Datasets ready in $DATASETS_DIR"
