#!/bin/bash
# 云服务器首次初始化（Ubuntu 22.04，root/密钥登录后执行一次）
# 用法：bash init-server.sh
set -euo pipefail

echo "== 1. 基础包 =="
apt-get update -qq
apt-get install -y -qq ca-certificates curl git >/dev/null

echo "== 2. Docker（官方源最新版） =="
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "== 3. swap 4G（2C4G 内存保险） =="
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 4. 内核参数（合成数据跑批友好） =="
cat > /etc/sysctl.d/99-fieldforge.conf <<'EOF'
vm.swappiness=10
net.core.somaxconn=1024
EOF
sysctl --system >/dev/null

echo "== 完成。docker version: $(docker --version) | swap: $(swapon --show | awk '/swapfile/{print $3}')"
