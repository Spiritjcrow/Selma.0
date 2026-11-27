#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
root="$PWD"
[[ -n "${PREFIX:-}" && -x "$PREFIX/bin/pkg" ]] || { echo 'Run in native Termux.' >&2; exit 1; }
pkg install -y openjdk-21 aapt2 d8 apksigner zip curl util-linux coreutils
state="$HOME/.local/share/selma-home"
mkdir -p "$state"
[[ -L "$HOME/storage/downloads" ]] || { echo 'Grant Termux shared storage via termux-setup-storage first.' >&2; exit 1; }
exec 9>"$state/build.lock"
flock -n 9 || { echo 'Another build is running.' >&2; exit 1; }
tmp="$(mktemp -d "$state/build.XXXXXX")"; trap 'rm -rf "$tmp"' EXIT
sdk="$state/android-35.jar"
sdkhash=4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b
if ! echo "$sdkhash  $sdk" | sha256sum --check --status; then
  curl --fail --location --retry 2 https://raw.githubusercontent.com/Sable/android-platforms/master/android-35/android.jar -o "$tmp/platform.jar"
  echo "$sdkhash  $tmp/platform.jar" | sha256sum -c -
  mv "$tmp/platform.jar" "$sdk"
fi
mkdir -p "$tmp/assets"
cp -a "$root/assets/." "$tmp/assets/"
find "$tmp/assets" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$tmp/assets" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
cat "$root"/model/model.bin.part* > "$tmp/assets/model.bin"
(cd "$tmp" && sha256sum -c "$root/assets.sha256")
mkdir "$tmp/classes" "$tmp/dex"
javac -source 8 -target 8 -classpath "$sdk" -d "$tmp/classes" src/org/selma/home/*.java
jar cf "$tmp/input.jar" -C "$tmp/classes" .
d8 --min-api 29 --lib "$sdk" --output "$tmp/dex" "$tmp/input.jar"
aapt2 compile --dir res -o "$tmp/res.zip"
aapt2 link "$tmp/res.zip" -I "$sdk" --manifest AndroidManifest.xml -A "$tmp/assets" -o "$tmp/app.apk"
(cd "$tmp/dex" && zip -q "$tmp/app.apk" classes.dex)
if [[ ! -e "$state/signing" ]]; then
  mkdir "$tmp/signing"
  head -c 32 /dev/urandom | base64 > "$tmp/signing/pass"
  keytool -genkeypair -storetype PKCS12 -keystore "$tmp/signing/owner.p12" -storepass:file "$tmp/signing/pass" -keypass:file "$tmp/signing/pass" -alias owner -dname 'CN=Selma Home Owner' -keyalg RSA -keysize 3072 -validity 3650
  mv "$tmp/signing" "$state/signing"
fi
apksigner sign --ks "$state/signing/owner.p12" --ks-pass "file:$state/signing/pass" --out "$tmp/signed.apk" "$tmp/app.apk"
apksigner verify --verbose "$tmp/signed.apk"
dest="$HOME/storage/downloads/SelmaHome-owner.apk"
out="$(mktemp "$HOME/storage/downloads/.selma-XXXXXX")"
cp "$tmp/signed.apk" "$out" && mv -f "$out" "$dest"
sha256sum "$dest"

bash termux/theme.sh install
termux-open --view --content-type application/vnd.android.package-archive "$dest"
