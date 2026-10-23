#!/usr/bin/env bash
# Keep a local OpenRGB build with the Retro 87 patch up to date.
#
#   ./update-openrgb.sh           update if upstream OpenRGB or the patch changed
#   ./update-openrgb.sh --force   rebuild anyway
#
# Builds upstream OpenRGB master plus openrgb/retro87-openrgb.patch from this
# checkout in its own directory ($RETRO87_OPENRGB_DIR, default
# ~/.local/share/retro87-tools/openrgb), never in a development checkout. The
# installed binary (bin/openrgb) is replaced only after a successful build;
# then the retro87-openrgb unit is restarted. On failure the previous binary
# stays in use. install-kde.sh runs this daily through the user timer
# retro87-openrgb-update. Needs git, qmake6, make and OpenRGB's build
# dependencies (Qt 6, libusb, hidapi, mbedtls).
set -euo pipefail

tools="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
patch="$tools/openrgb/retro87-openrgb.patch"
root="${RETRO87_OPENRGB_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/retro87-tools/openrgb}"
upstream_url="${OPENRGB_UPSTREAM:-https://gitlab.com/CalcProgrammer1/OpenRGB.git}"
src="$root/src" build="$root/build" bin="$root/bin/openrgb" state="$root/state"
force=0
[[ "${1:-}" == "--force" ]] && force=1

log() { echo "update-openrgb: $*"; }
fail() {
    log "FAILED: $*; still using the previous build"
    command -v notify-send >/dev/null && notify-send -a "Retro 87" -i input-keyboard \
        "OpenRGB update failed" "$*. The previous build is still in use; see journalctl --user -u retro87-openrgb-update." || true
    exit 1
}

mkdir -p "$root/bin"
exec 9>"$root/lock"
flock -n 9 || { log "another update is running"; exit 0; }

for tool in git qmake6 make; do
    command -v "$tool" >/dev/null || fail "$tool is not installed"
done
[[ -f "$patch" ]] || fail "patch not found: $patch"

if [[ ! -d "$src/.git" ]]; then
    log "cloning upstream OpenRGB"
    git clone -q --depth 50 --branch master "$upstream_url" "$src" || fail "cannot clone $upstream_url"
fi
git -C "$src" fetch -q --depth 50 origin master || fail "cannot fetch upstream OpenRGB"
upstream=$(git -C "$src" rev-parse --short=10 FETCH_HEAD)
patch_id=$(sha256sum "$patch" | cut -c1-10)
wanted="upstream=$upstream patch=$patch_id"

if [[ $force == 0 && -x "$bin" && "$(cat "$state" 2>/dev/null)" == "$wanted" ]]; then
    log "up to date ($wanted)"
    exit 0
fi

log "building $wanted"
# The source tree belongs to this script: reset it to upstream, then patch.
git -C "$src" checkout -q --force --detach FETCH_HEAD
git -C "$src" clean -q -fdx
git -C "$src" apply "$patch" || fail "the patch does not apply to upstream $upstream"

mkdir -p "$build"
(cd "$build" && qmake6 "$src/OpenRGB.pro" >/dev/null && make -j"$(nproc)" >"$root/make.log" 2>&1) \
    || fail "build failed (log: $root/make.log)"
"$build/openrgb" --version >/dev/null 2>&1 || fail "the new build does not start"

cp "$build/openrgb" "$bin.new"
mv -f "$bin.new" "$bin"
echo "$wanted" > "$state"
log "installed $bin ($wanted)"

if systemctl --user is-enabled --quiet retro87-openrgb.service 2>/dev/null; then
    systemctl --user restart retro87-openrgb.service
    log "restarted retro87-openrgb"
fi
