"""Source-level regression checks; not an Android build or device integration test."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DIR=Path(__file__).resolve().parent

MOCK={
 'app/build.gradle.kts': '''val playBuild = providers.gradleProperty("playBuild").orNull?.toBoolean() == true ||
        ndk.abiFilters += "arm64-v8a"
        buildConfigString(appUpdateManifestUrl)
''',
 'app/src/main/cpp/CMakeLists.txt': '''if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Mobile Harness currently supports only arm64-v8a")
endif()
''',
 'app/src/main/java/com/jarves/mh/MainActivity.kt': '''import android.os.Bundle
    private var appliedLanguageCode: String? = null
        enableEdgeToEdge()
        setContent {
    override fun onTrimMemory(level: Int) {
        if (level >= ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW) {
''',
 'app/src/main/java/com/jarves/mh/ui/MainViewModel.kt': '''private const val MAX_VISIBLE_WORK_ITEMS = 32
private const val MAX_ACTIVITY_DETAIL_CHARS = 8_000
private const val MAX_EDITABLE_FILE_BYTES = 512_000L
private const val MAX_PROJECT_TERMINAL_HISTORY = 100
private const val MAX_PROJECT_TERMINAL_OUTPUT = 200_000
private const val MAX_ANDROID_BUILD_LOG = 300_000
private const val MAX_LOGCAT_LINES = 5_000
private const val MAX_PROCESS_OUTPUT_BYTES = 512 * 1024
private const val MAX_ATTACHMENT_BYTES = 25L * 1024L * 1024L
''',
 'app/src/main/java/com/jarves/mh/ui/PocketDevApp.kt': '''                        Text(
                            stringResource(R.string.runtime_setup_download_based_on_tools),
'''
}

class PatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=Path(self.tmp.name)
  for path, content in MOCK.items():
   p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 def tearDown(self):self.tmp.cleanup()
 def apply(self):
  return subprocess.run([sys.executable,str(DIR/'apply_moto_lite.py')],cwd=self.root,capture_output=True,text=True)
 def test_patch_application(self):
  result=self.apply();self.assertEqual(result.returncode,0,result.stderr)
  c=(self.root/'app/build.gradle.kts').read_text()
  self.assertIn('armeabi-v7a',c);self.assertIn('com.jarves.mh', 'com.jarves.mh')
  self.assertIn('applicationIdSuffix = ".motolite"',c)
 def test_reapply_idempotent(self):
  self.assertEqual(self.apply().returncode,0)
  first={k:(self.root/k).read_text() for k in MOCK}
  self.assertEqual(self.apply().returncode,0)
  self.assertEqual(first,{k:(self.root/k).read_text() for k in MOCK})
 def test_fallback_not_fake_proot(self):
  self.assertEqual(self.apply().returncode,0)
  cmake=(self.root/'app/src/main/cpp/CMakeLists.txt').read_text()
  self.assertIn('add_library(pocketspawn SHARED pocket_spawn.c)',cmake)
  self.assertIn('return()',cmake)
  main=(self.root/'app/src/main/java/com/jarves/mh/MainActivity.kt').read_text()
  self.assertIn('MotoLiteEditorApp()',main)
  src=(self.root/'app/src/main/java/com/jarves/mh/ui/MotoLiteEditor.kt').read_text()
  self.assertIn('blockNetworkLoads = true',src)
  self.assertIn('Save copy',src)
 def test_fails_safe_on_wrong_tag(self):
  p=self.root/'app/build.gradle.kts';p.write_text('not the source')
  result=self.apply();self.assertNotEqual(result.returncode,0)
 def test_moto_memory_limits(self):
  self.assertEqual(self.apply().returncode,0)
  v=(self.root/'app/src/main/java/com/jarves/mh/ui/MainViewModel.kt').read_text()
  self.assertIn('MOTO_LITE_BUILD) 40 else 100',v)
  self.assertIn('MOTO_LITE_BUILD) 300 else 5_000',v)

if __name__=='__main__':unittest.main(verbosity=2)