#!/bin/bash
# Run on a Mac with Developer ID Installer and a notarytool keychain profile.
set -euo pipefail
: "${SRT_INSTALLER_IDENTITY:?Set Developer ID Installer certificate identity}"
: "${SRT_NOTARY_PROFILE:?Set existing notarytool keychain profile}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
node "$ROOT/tools/build-release.cjs"
VERSION="$(node -p "require(process.argv[1]).version" "$ROOT/plugin/package.json")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/rambla-srt-pkg.XXXXXX")"
trap 'case "$WORK" in */rambla-srt-pkg.*) rm -rf -- "$WORK";; esac' EXIT
PAYLOAD='/Library/Application Support/RAMBLA/SRT Installer'
mkdir -p "$WORK/root$PAYLOAD" "$WORK/scripts"
cp -R "$ROOT/dist/RAMBLA-SRT-$VERSION/." "$WORK/root$PAYLOAD/"
cat > "$WORK/scripts/postinstall" <<'POSTINSTALL'
#!/bin/bash
set -euo pipefail
# Installer executes as root; hand ownership only to the interactive console user.
export SUDO_UID="$(stat -f %u /dev/console)"
export SUDO_GID="$(stat -f %g /dev/console)"
exec /bin/bash '/Library/Application Support/RAMBLA/SRT Installer/install/install-mac.sh' --quiet
POSTINSTALL
chmod 755 "$WORK/scripts/postinstall" "$WORK/root$PAYLOAD/INSTALLA_MAC.command"
pkgbuild --root "$WORK/root" --scripts "$WORK/scripts" --identifier com.rambla.srt.installer --version "$VERSION" --install-location / "$WORK/unsigned.pkg"
PKG="$ROOT/dist/RAMBLA-SRT-$VERSION-mac.pkg"
productsign --sign "$SRT_INSTALLER_IDENTITY" "$WORK/unsigned.pkg" "$PKG"
xcrun notarytool submit "$PKG" --keychain-profile "$SRT_NOTARY_PROFILE" --wait
xcrun stapler staple "$PKG"
pkgutil --check-signature "$PKG"
spctl --assess --type install --verbose "$PKG"
echo "Firmato e notarizzato: $PKG"
