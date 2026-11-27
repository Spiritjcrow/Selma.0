#!/usr/bin/env bash
set -euo pipefail
umask 077

root="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$root/build/host}"
apk_base="${SELMA_APK_BASENAME:-SelmaHome-0.4.0-owner}"
[[ "$apk_base" != */* && -n "$apk_base" ]] || { echo "Invalid SELMA_APK_BASENAME." >&2; exit 2; }
android_jar="${ANDROID_JAR:-${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}/platforms/android-35/android.jar}"
build_tools="${ANDROID_BUILD_TOOLS:-}"

[[ -r "$android_jar" ]] || { echo "Set ANDROID_JAR to Android SDK Platform 35 android.jar." >&2; exit 2; }
if [[ -z "$build_tools" ]]; then
  sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
  [[ -d "$sdk_root/build-tools" ]] || { echo "Set ANDROID_BUILD_TOOLS to Android Build Tools 35." >&2; exit 2; }
  build_tools="$(find "$sdk_root/build-tools" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V | tail -1)"
  build_tools="$sdk_root/build-tools/$build_tools"
fi
for tool in aapt2 d8 apksigner zipalign; do
  [[ -x "$build_tools/$tool" ]] || { echo "Missing $build_tools/$tool" >&2; exit 2; }
done
command -v zip >/dev/null

if command -v javac >/dev/null; then
  javac_cmd=(javac)
else
  java --list-modules | grep -q '^jdk.compiler@'
  javac_cmd=(java -m jdk.compiler/com.sun.tools.javac.Main)
fi
if command -v jar >/dev/null; then
  jar_cmd=(jar)
else
  java --list-modules | grep -q '^jdk.jartool@'
  jar_cmd=(java -m jdk.jartool/sun.tools.jar.Main)
fi

rm -rf "$out"
mkdir -p "$out/classes" "$out/dex"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/selma-home.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/assets"
cp -a "$root/assets/." "$tmp/assets/"
find "$tmp/assets" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$tmp/assets" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
cat "$root"/model/model.bin.part* > "$tmp/assets/model.bin"
(cd "$tmp" && sha256sum -c "$root/assets.sha256")
"${javac_cmd[@]}" -source 8 -target 8 -classpath "$android_jar" \
  -d "$out/classes" "$root"/src/org/selma/home/*.java
"${jar_cmd[@]}" cf "$out/input.jar" -C "$out/classes" .
"$build_tools/d8" --min-api 29 --lib "$android_jar" --output "$out/dex" "$out/input.jar"
"$build_tools/aapt2" compile --dir "$root/res" -o "$out/resources.zip"
"$build_tools/aapt2" link "$out/resources.zip" -I "$android_jar" \
  --manifest "$root/AndroidManifest.xml" -A "$tmp/assets" -o "$tmp/unsigned.apk"
(cd "$out/dex" && zip -X -q "$tmp/unsigned.apk" classes.dex)
"$build_tools/zipalign" -f 4 "$tmp/unsigned.apk" "$out/$apk_base-unsigned.apk"

if [[ -n "${SELMA_KEYSTORE:-}" ]]; then
  [[ -r "$SELMA_KEYSTORE" && -r "${SELMA_KEYPASS_FILE:-}" ]] || {
    echo "SELMA_KEYSTORE requires readable SELMA_KEYPASS_FILE." >&2; exit 2;
  }
  "$build_tools/apksigner" sign --ks "$SELMA_KEYSTORE" \
    --ks-pass "file:$SELMA_KEYPASS_FILE" \
    --out "$out/$apk_base.apk" "$out/$apk_base-unsigned.apk"
  "$build_tools/apksigner" verify --verbose --print-certs "$out/$apk_base.apk"
  sha256sum "$out/$apk_base.apk"
else
  sha256sum "$out/$apk_base-unsigned.apk"
fi
