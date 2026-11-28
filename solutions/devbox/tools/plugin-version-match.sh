#!/usr/bin/env bash
# =============================================================================
# plugin-version-match.sh —— 插件与 DSH/Magpie 目标版本自动匹配（TD-006 任务③ / D28）
#
# 用法：
#   plugin-version-match.sh <插件名> [--core <核心包名>] [--dsh <版本>] [--magpie <版本>] [--cordis <版本>] [--json]
#
#   <插件名>   必填，npm 包名（如 dsh-voice-mode、@magpie-community/tools-calc）
#   --core     插件 peer 的核心库包名（默认 @deepseek-ai/cordis；magpie 插件传 magpie 核心包）
#   --dsh      目标 DSH 版本（默认取本机 `dsh --version`；如 0.2.2-rc.5）
#   --magpie   目标 Magpie 版本（默认取本机 `magpie --version`）
#   --cordis   核心库实际版本（默认自动探测本机安装；如 4.2.0）
#   --json     以 JSON 输出完整匹配矩阵
#
# 匹配规则（默认策略：兼容相邻小版本升级）：
#   1) 逐版本读取插件 peerDependencies（npm view <pkg>@<v> peerDependencies --json）；
#   2) peer 为核心库 semver range（如 @deepseek-ai/cordis ^4.0.1）→ 用核心库实际版本判定；
#   3) peer 为宿主白名单形态（@deepseek-ai/dsh-* 列候选版本串）→ 用 DSH 目标版本显式命中判定；
#   4) 无 peer 声明 → 相邻小版本兼容策略（^最新版，reason=fallback-minor）；
#   5) 输出兼容的最大插件版本；--json 输出匹配矩阵。退出码 0=有推荐，4=无兼容版本。
# =============================================================================
set -euo pipefail

PLUGIN=""; CORE="@deepseek-ai/cordis"; DSH_VER=""; MAGPIE_VER=""; CORDIS_VER=""; JSON_OUT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --core) CORE="$2"; shift 2 ;;
    --dsh) DSH_VER="$2"; shift 2 ;;
    --magpie) MAGPIE_VER="$2"; shift 2 ;;
    --cordis) CORDIS_VER="$2"; shift 2 ;;
    --json) JSON_OUT=1; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) if [ -z "$PLUGIN" ]; then PLUGIN="$1"; else echo "多余参数: $1" >&2; exit 2; fi; shift ;;
  esac
done
[ -n "$PLUGIN" ] || { echo "用法: $0 <插件名> [--core <核心包>] [--dsh <版本>] [--magpie <版本>] [--cordis <版本>] [--json]" >&2; exit 2; }

NODE_BIN="$(command -v node || ls /opt/nvm/versions/node/*/bin/node 2>/dev/null | head -1 || true)"
[ -n "$NODE_BIN" ] || { echo "未找到 node（semver 依赖 npm 内置包）" >&2; exit 3; }
NPM="$(dirname "$NODE_BIN")/npm"

if [ -z "$DSH_VER" ] && command -v dsh >/dev/null 2>&1; then
  DSH_VER="$(dsh --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*' | head -1 || true)"
fi
if [ -z "$MAGPIE_VER" ] && command -v magpie >/dev/null 2>&1; then
  MAGPIE_VER="$(magpie --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*' | head -1 || true)"
fi
if [ -z "$CORDIS_VER" ]; then
  # 自动探测本机核心库实际版本（npm 全局树或 dsh 嵌套依赖）
  CORDIS_VER="$(find "$(npm root -g 2>/dev/null || echo /nonexist)" /opt/nvm -path "*/node_modules/${CORE}/package.json" 2>/dev/null | head -1 | xargs -r grep -o '"version": *"[^"]*"' | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^"]*' || true)"
fi
[ -n "$DSH_VER" ] || { echo "未提供 --dsh 且本机无 dsh 可执行" >&2; exit 2; }
[ -n "$CORDIS_VER" ] || CORDIS_VER="0.0.0"  # 探测失败时 range 判定一律不满足，只走白名单/回退路径

"$NODE_BIN" - "$PLUGIN" "$CORE" "$DSH_VER" "$MAGPIE_VER" "$CORDIS_VER" "$JSON_OUT" <<'JSEOF'
const [plugin, core, dshVer, magpieVer, coreVer, , jsonOut] = process.argv.slice(2);
const jsonFlag = jsonOut === '1';
const { execFileSync } = require('child_process');
let semver;
try { semver = require(require('path').join(execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim(), 'npm/node_modules/semver')); }
catch { try { semver = require('semver'); } catch { semver = null; } }

function npmView(args) {
  try { return JSON.parse(execFileSync('npm', ['view', ...args, '--json'], { timeout: 30000, encoding: 'utf8' })); }
  catch (e) { return null; }
}
function checkCompat(pkgVer) {
  const peers = npmView([`${plugin}@${pkgVer}`, 'peerDependencies']);
  if (!peers) return { ver: pkgVer, compat: null, reason: 'peer-query-failed' };
  const range = peers[core];
  if (range && semver) {
    const target = semver.coerce(coreVer);
    const ok = target && semver.satisfies(target, range);
    return { ver: pkgVer, compat: !!ok, reason: `peer ${core} ${range} vs 实际 ${coreVer} → ${ok ? '满足' : '不满足'}` };
  }
  // 白名单形态：宿主系 peer（dsh-*/magpie）候选串显式包含目标 DSH/Magpie 版本
  for (const [pkg, val] of Object.entries(peers)) {
    const isDsh = pkg.startsWith('@deepseek-ai/dsh') || pkg.startsWith('@deepseek-ai/cordis');
    const isMagpie = /magpie/i.test(pkg);
    if (!isDsh && !isMagpie) continue;
    const target = isMagpie && magpieVer ? magpieVer : dshVer;
    const cands = String(val).split(/\s*\|\|\s*/).map(s => s.trim());
    if (cands.some(c => c === target)) return { ver: pkgVer, compat: true, reason: `${pkg} 白名单显式包含 ${target}` };
  }
  if (Object.keys(peers).length === 0) return { ver: pkgVer, compat: true, reason: '无 peer 声明 → 相邻小版本兼容策略（fallback-minor）' };
  return { ver: pkgVer, compat: null, reason: `peer 依赖不含宿主白名单且无 ${core} range 可判` };
}

const versions = npmView([plugin, 'versions']);
if (!versions) { console.error(`npm 查询失败: ${plugin}`); process.exit(1); }
const list = (Array.isArray(versions) ? versions : [versions]).reverse();
// 从最新往回找到第一个兼容版本即停（避免全版本逐个 npm view；--json 时限前 30 个）
const limit = jsonFlag ? 30 : list.length;
const matrix = [];
let best = null;
for (let i = 0; i < Math.min(limit, list.length); i++) {
  const m = checkCompat(list[i]);
  matrix.push(m);
  if (m.compat === true) { best = m; break; }
}
const out = {
  plugin, core, dshTarget: dshVer, magpieTarget: magpieVer || null, coreLibVersion: coreVer,
  recommended: best ? best.ver : null,
  strategy: best ? best.reason : '无兼容版本（考虑升级插件、升级核心库或降级宿主）',
  matrix: jsonFlag ? matrix : matrix.filter(m => m.compat !== null).slice(0, 5),
};
console.log(jsonFlag ? JSON.stringify(out, null, 2) :
  `推荐版本: ${out.recommended || '(无)'}\n原因: ${out.strategy}\n核心库实际版本: ${coreVer}\n近邻矩阵:\n` +
  out.matrix.map(m => `  ${m.ver}  ${m.compat === true ? '兼容' : m.compat === false ? '不兼容' : '未知'}  ${m.reason}`).join('\n'));
process.exit(out.recommended ? 0 : 4);
JSEOF
