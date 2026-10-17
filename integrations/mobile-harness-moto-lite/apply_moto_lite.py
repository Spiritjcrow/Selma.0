#!/usr/bin/env python3
"""Apply a source-level low-RAM/ARMv7 fallback patch to Mobile Harness v1.0.7.
Run at the checked-out upstream repo root. Deliberately does not fake ARM64 Linux runtime.
"""
from pathlib import Path
import sys

ROOT = Path.cwd()
SOURCE = Path(__file__).resolve().parent / 'MotoLiteEditor.kt'


def replace(path, old, new):
    p = ROOT / path
    if not p.is_file():
        raise RuntimeError(f'Required upstream source missing: {p}')
    data = p.read_text()
    if new in data:
        print(f'Already modified: {path}')
        return
    if data.count(old) != 1:
        raise RuntimeError(f'Upstream v1.0.7 mismatch in {path} (count={data.count(old)}); aborting instead of guessing')
    p.write_text(data.replace(old, new, 1))
    print(f'Modified: {path}')


def main():
    if not (ROOT / 'app/build.gradle.kts').is_file():
        sys.exit('Run this script from the Mobile-Harness project root.')
    build = 'app/build.gradle.kts'
    replace(build,
            'val playBuild = providers.gradleProperty("playBuild").orNull?.toBoolean() == true ||',
            'val motoLite = providers.gradleProperty("motoLite").orNull?.toBoolean() == true\nval playBuild = providers.gradleProperty("playBuild").orNull?.toBoolean() == true ||')
    replace(build,
            '        ndk.abiFilters += "arm64-v8a"',
            '        // Motorola Lite can *install* on ARMv7; ARMv7 uses the native editor,\n'
            '        // never the ARM64 PRoot/Ubuntu/Claude runtime.\n'
            '        if (motoLite) {\n'
            '            applicationIdSuffix = ".motolite"\n'
            '            versionNameSuffix = "-moto-lite"\n'
            '            ndk.abiFilters += listOf("arm64-v8a", "armeabi-v7a")\n'
            '        } else {\n'
            '            ndk.abiFilters += "arm64-v8a"\n'
            '        }\n'
            '        buildConfigField("boolean", "MOTO_LITE_BUILD", motoLite.toString())')
    replace(build,
            'buildConfigString(appUpdateManifestUrl)',
            'buildConfigString(if (motoLite) "" else appUpdateManifestUrl)')
    cmake = 'app/src/main/cpp/CMakeLists.txt'
    replace(cmake,
            'if(NOT ANDROID_ABI STREQUAL "arm64-v8a")\n    message(FATAL_ERROR "Mobile Harness currently supports only arm64-v8a")\nendif()',
            'if(ANDROID_ABI STREQUAL "armeabi-v7a")\n'
            '    # 32-bit Android shell: support native UI only, NO PRoot runtime.\n'
            '    add_library(pocketspawn SHARED pocket_spawn.c)\n'
            '    return()\n'
            'elseif(NOT ANDROID_ABI STREQUAL "arm64-v8a")\n'
            '    message(FATAL_ERROR "Unsupported native ABI")\n'
            'endif()')
    activity = 'app/src/main/java/com/jarves/mh/MainActivity.kt'
    replace(activity,
            'import android.os.Bundle',
            'import android.os.Bundle\nimport android.os.Build\nimport com.jarves.mh.runtime.supportsArm64Runtime\nimport com.jarves.mh.ui.MotoLiteEditorApp')
    replace(activity,
            '    private var appliedLanguageCode: String? = null',
            '    private var appliedLanguageCode: String? = null\n    private var motoLiteEditorOnly = false')
    replace(activity,
            '        enableEdgeToEdge()\n        setContent {',
            '        enableEdgeToEdge()\n'
            '        // 32-bit userspace cannot execute the upstream ARM64 rootfs. Instead\n'
            '        // start a functional SAF-based native editor without instantiating\n'
            '        // the PRoot or AI agent controllers.\n'
            '        motoLiteEditorOnly = BuildConfig.MOTO_LITE_BUILD &&\n'
            '            !supportsArm64Runtime(Build.SUPPORTED_ABIS, System.getProperty("os.arch"))\n'
            '        if (motoLiteEditorOnly) {\n'
            '            setContent { MotoLiteEditorApp() }\n'
            '            return\n'
            '        }\n'
            '        setContent {')
    replace(activity,
            '        if (level >= ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW) {',
            '        if (!motoLiteEditorOnly && level >= ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW) {')
    replace(activity,
            '    override fun onTrimMemory(level: Int) {',
            '    override fun onLowMemory() {\n'
            '        super.onLowMemory()\n'
            '        if (!motoLiteEditorOnly) mainViewModel.releaseMemoryCaches()\n'
            '    }\n\n'
            '    override fun onTrimMemory(level: Int) {')

    viewmodel = 'app/src/main/java/com/jarves/mh/ui/MainViewModel.kt'
    budgets = {
        'private const val MAX_VISIBLE_WORK_ITEMS = 32': 'private val MAX_VISIBLE_WORK_ITEMS = if (BuildConfig.MOTO_LITE_BUILD) 12 else 32',
        'private const val MAX_ACTIVITY_DETAIL_CHARS = 8_000': 'private val MAX_ACTIVITY_DETAIL_CHARS = if (BuildConfig.MOTO_LITE_BUILD) 2_000 else 8_000',
        'private const val MAX_EDITABLE_FILE_BYTES = 512_000L': 'private val MAX_EDITABLE_FILE_BYTES = if (BuildConfig.MOTO_LITE_BUILD) 256_000L else 512_000L',
        'private const val MAX_PROJECT_TERMINAL_HISTORY = 100': 'private val MAX_PROJECT_TERMINAL_HISTORY = if (BuildConfig.MOTO_LITE_BUILD) 40 else 100',
        'private const val MAX_PROJECT_TERMINAL_OUTPUT = 200_000': 'private val MAX_PROJECT_TERMINAL_OUTPUT = if (BuildConfig.MOTO_LITE_BUILD) 48_000 else 200_000',
        'private const val MAX_ANDROID_BUILD_LOG = 300_000': 'private val MAX_ANDROID_BUILD_LOG = if (BuildConfig.MOTO_LITE_BUILD) 48_000 else 300_000',
        'private const val MAX_LOGCAT_LINES = 5_000': 'private val MAX_LOGCAT_LINES = if (BuildConfig.MOTO_LITE_BUILD) 300 else 5_000',
        'private const val MAX_PROCESS_OUTPUT_BYTES = 512 * 1024': 'private val MAX_PROCESS_OUTPUT_BYTES = if (BuildConfig.MOTO_LITE_BUILD) 64 * 1024 else 512 * 1024',
        'private const val MAX_ATTACHMENT_BYTES = 25L * 1024L * 1024L': 'private val MAX_ATTACHMENT_BYTES = if (BuildConfig.MOTO_LITE_BUILD) 6L * 1024L * 1024L else 25L * 1024L * 1024L',
    }
    for old,new in budgets.items(): replace(viewmodel,old,new)
    pocket = 'app/src/main/java/com/jarves/mh/ui/PocketDevApp.kt'
    replace(pocket,
            '                        Text(\n                            stringResource(R.string.runtime_setup_download_based_on_tools),',
            '                        if (com.jarves.mh.BuildConfig.MOTO_LITE_BUILD && totalRamGb < 4.0) {\n'
            '                            Text(\n'
            '                                "Moto Lite (3 GB): start with Core/Web only. Install Python later " +\n'
            '                                    "if space allows. Run APK compilation and large AI models " +\n'
            '                                    "on a computer/cloud workspace.",\n'
            '                                fontSize = 12.sp,\n'
            '                                color = MaterialTheme.colorScheme.onSurfaceVariant,\n'
            '                            )\n'
            '                        }\n'
            '                        Text(\n                            stringResource(R.string.runtime_setup_download_based_on_tools),')
    dest = ROOT / 'app/src/main/java/com/jarves/mh/ui/MotoLiteEditor.kt'
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_text() != SOURCE.read_text():
        raise RuntimeError(f'Existing file differs: {dest}')
    dest.write_text(SOURCE.read_text())
    print('Added:', dest.relative_to(ROOT))
    print('Moto Lite patch complete. Build ONLINE profile only: ./gradlew -PmotoLite=true :app:assembleOnlineDebug')


if __name__ == '__main__':
    main()