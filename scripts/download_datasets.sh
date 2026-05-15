#!/bin/bash
# Download benchmark datasets for SLOBF
# Target: coreutils + binutils + diffutils + findutils

set -e

DATASETS_DIR="datasets/raw"
mkdir -p "$DATASETS_DIR"

# ------------------------------------------------------------------
# Coreutils 9.1
# ------------------------------------------------------------------
COREUTILS_VER="9.1"
COREUTILS_URL="https://ftp.gnu.org/gnu/coreutils/coreutils-${COREUTILS_VER}.tar.xz"
if [ ! -d "$DATASETS_DIR/coreutils" ]; then
    echo "[1/4] Downloading Coreutils ${COREUTILS_VER}..."
    wget -c "$COREUTILS_URL" -P "$DATASETS_DIR"
    tar -xf "$DATASETS_DIR/coreutils-${COREUTILS_VER}.tar.xz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/coreutils-${COREUTILS_VER}" "$DATASETS_DIR/coreutils"
    rm "$DATASETS_DIR/coreutils-${COREUTILS_VER}.tar.xz"
else
    echo "[1/4] Coreutils already exists."
fi

# ------------------------------------------------------------------
# Binutils 2.41
# ------------------------------------------------------------------
BINUTILS_VER="2.41"
BINUTILS_URL="https://ftp.gnu.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.xz"
if [ ! -d "$DATASETS_DIR/binutils" ]; then
    echo "[2/4] Downloading Binutils ${BINUTILS_VER}..."
    wget -c "$BINUTILS_URL" -P "$DATASETS_DIR"
    tar -xf "$DATASETS_DIR/binutils-${BINUTILS_VER}.tar.xz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/binutils-${BINUTILS_VER}" "$DATASETS_DIR/binutils"
    rm "$DATASETS_DIR/binutils-${BINUTILS_VER}.tar.xz"
else
    echo "[2/4] Binutils already exists."
fi

# ------------------------------------------------------------------
# Diffutils 3.10
# ------------------------------------------------------------------
DIFFUTILS_VER="3.10"
DIFFUTILS_URL="https://ftp.gnu.org/gnu/diffutils/diffutils-${DIFFUTILS_VER}.tar.xz"
if [ ! -d "$DATASETS_DIR/diffutils" ]; then
    echo "[3/4] Downloading Diffutils ${DIFFUTILS_VER}..."
    wget -c "$DIFFUTILS_URL" -P "$DATASETS_DIR"
    tar -xf "$DATASETS_DIR/diffutils-${DIFFUTILS_VER}.tar.xz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/diffutils-${DIFFUTILS_VER}" "$DATASETS_DIR/diffutils"
    rm "$DATASETS_DIR/diffutils-${DIFFUTILS_VER}.tar.xz"
else
    echo "[3/4] Diffutils already exists."
fi

# ------------------------------------------------------------------
# Findutils 4.9.0
# ------------------------------------------------------------------
FINDUTILS_VER="4.9.0"
FINDUTILS_URL="https://ftp.gnu.org/gnu/findutils/findutils-${FINDUTILS_VER}.tar.xz"
if [ ! -d "$DATASETS_DIR/findutils" ]; then
    echo "[4/4] Downloading Findutils ${FINDUTILS_VER}..."
    wget -c "$FINDUTILS_URL" -P "$DATASETS_DIR"
    tar -xf "$DATASETS_DIR/findutils-${FINDUTILS_VER}.tar.xz" -C "$DATASETS_DIR"
    mv "$DATASETS_DIR/findutils-${FINDUTILS_VER}" "$DATASETS_DIR/findutils"
    rm "$DATASETS_DIR/findutils-${FINDUTILS_VER}.tar.xz"
else
    echo "[4/4] Findutils already exists."
fi

echo ""
echo "Datasets ready in $DATASETS_DIR"
echo "  coreutils  ${COREUTILS_VER}  (~100 programs)"
echo "  binutils   ${BINUTILS_VER}   (~20 programs)"
echo "  diffutils  ${DIFFUTILS_VER}  (4 programs)"
echo "  findutils  ${FINDUTILS_VER}  (4 programs)"
echo "  Total: ~128 GNU utility programs"
