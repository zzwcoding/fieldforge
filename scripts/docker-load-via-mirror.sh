#!/bin/bash
# 一次性脚本：从 docker.1ms.run 用 curl 拉 ubuntu:24.04 (arm64) blob 并组装 OCI tar
set -euo pipefail
CURL=/usr/bin/curl
REF=library/ubuntu
TAG=24.04
OCI=/tmp/oci
mkdir -p "$OCI/blobs/sha256"

TOK=$($CURL -s --max-time 10 "https://docker.1ms.run/openapi/v1/auth/token?service=docker.1ms.run&scope=repository:$REF:pull" | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
[ -n "$TOK" ] || { echo "token 获取失败"; exit 1; }

ACCEPT="Accept: application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"

$CURL -sL --max-time 60 -H "Authorization: Bearer $TOK" -H "$ACCEPT" \
  "https://docker.1ms.run/v2/$REF/manifests/$TAG" -o "$OCI/ml.json"

DIG=$(python3 - "$OCI/ml.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ms = d.get('manifests', [])
pick = [m for m in ms if m.get('platform', {}).get('os') == 'linux' and m.get('platform', {}).get('architecture') == 'arm64']
print(pick[0]['digest'] if pick else (ms[0]['digest'] if ms else ''))
PY
)
[ -n "$DIG" ] || { echo "找不到 arm64 manifest"; exit 1; }
echo "arm64 manifest: $DIG"

$CURL -sL --max-time 60 -H "Authorization: Bearer $TOK" -H "$ACCEPT" \
  "https://docker.1ms.run/v2/$REF/manifests/$DIG" -o "$OCI/man.json"

export TOK
python3 - "$DIG" "$REF" <<'PY'
import json, os, subprocess, sys, hashlib

dig, ref = sys.argv[1], sys.argv[2]
curl = '/usr/bin/curl'
tok = os.environ['TOK']

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()

oci = '/tmp/oci'
assert sha256(f'{oci}/man.json') == dig, 'manifest sha 校验失败'
m = json.load(open(f'{oci}/man.json'))
media = m.get('mediaType', '')
print('manifest mediaType:', media)
blobs = [(m['config']['digest'], m['config']['size'])] + [(l['digest'], l['size']) for l in m['layers']]
print(f'{len(blobs)} 个 blob，共 {sum(s for _, s in blobs)/1e6:.1f} MB')

for d, size in blobs:
    hexd = d.split(':')[1]
    path = f'{oci}/blobs/sha256/{hexd}'
    if os.path.exists(path) and sha256(path) == d:
        print(f'  ✓ 已存在 {hexd[:12]}')
        continue
    url = f'https://docker.1ms.run/v2/{ref}/blobs/{d}'
    r = subprocess.run([curl, '-sL', '--max-time', '600', '-H', f'Authorization: Bearer {tok}', url, '-o', path])
    if r.returncode != 0:
        sys.exit(f'curl 失败 {hexd[:12]} rc={r.returncode}')
    if os.path.getsize(path) != size or sha256(path) != d:
        sys.exit(f'校验失败 {hexd[:12]}')
    print(f'  ✓ {hexd[:12]} ({size/1e6:.1f} MB)')

# 组装 OCI layout
layout = f'{oci}/oci-layout'
if not os.path.exists(layout):
    open(layout, 'w').write('{"imageLayoutVersion":"1.0.0"}')
index = {
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.index.v1+json",
    "manifests": [{
        "mediaType": media or "application/vnd.docker.distribution.manifest.v2+json",
        "digest": dig,
        "size": os.path.getsize(f'{oci}/man.json'),
        "annotations": {"org.opencontainers.image.ref.name": "ubuntu:24.04"},
    }],
}
open(f'{oci}/index.json', 'w').write(json.dumps(index))
print('OCI layout 组装完成')
PY

tar -C "$OCI" -cf /tmp/ubuntu2404-arm64.tar . 
echo "tar: $(du -h /tmp/ubuntu2404-arm64.tar | awk '{print $1}') → docker load"
