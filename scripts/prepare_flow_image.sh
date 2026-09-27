#!/bin/bash
# 构建 fieldforge/flow:2026.04 —— OPM Flow 容器镜像（M2-T1 扫参运行环境）
#
# GPL-3.0 红线（charter §5）：OPM 组件只在独立容器内运行，宿主仅经命令行与文件交换，
# 不链接其源码、不二次分发。
#
# 用法: bash scripts/prepare_flow_image.sh
set -euo pipefail
IMG=fieldforge/flow:2026.04
C=flowprep-$$

docker rm -f "$C" >/dev/null 2>&1 || true
docker run -d --name "$C" ubuntu:24.04 sleep infinity >/dev/null

docker exec "$C" bash -c '
set -e
sed -i "s|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g" /etc/apt/sources.list.d/ubuntu.sources
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq gnupg curl software-properties-common >/dev/null
add-apt-repository -y ppa:opm/ppa >/dev/null
apt-get update -qq
apt-get install -y -qq libopm-simulators-bin >/dev/null
flow --version | head -1
'

docker commit "$C" "$IMG" >/dev/null
docker rm -f "$C" >/dev/null
echo "镜像就绪: $IMG"
