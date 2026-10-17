package com.jarves.mh.ui

import android.net.Uri
import android.provider.OpenableColumns
import android.webkit.WebView
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import java.io.ByteArrayOutputStream
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Genuine fallback for Android 32-bit devices. No synthetic terminal, fake
 * agent output, PRoot or privilege escalation. Files remain under SAF grants.
 * Offline HTML previews disable JS, remote network loads and local file access.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MotoLiteEditorApp() {
    val context = LocalContext.current
    var content by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("new-file.txt") }
    var status by remember { mutableStateOf("Native editor mode: Linux agents unavailable on 32-bit Android") }
    var preview by remember { mutableStateOf(false) }
    val maxBytes = 256 * 1024

    val open = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                context.contentResolver.openAssetFileDescriptor(uri, "r")?.use { descriptor ->
                    require(descriptor.length < 0 || descriptor.length <= maxBytes) {
                        "File exceeds the 256 KB editor limit"
                    }
                }
                val bytes = context.contentResolver.openInputStream(uri)?.use { source ->
                    val buffer = ByteArray(8192)
                    val sink = ByteArrayOutputStream()
                    while (true) {
                        val count = source.read(buffer)
                        if (count < 0) break
                        require(sink.size() + count <= maxBytes) { "File exceeds 256 KB" }
                        sink.write(buffer, 0, count)
                    }
                    sink.toByteArray()
                } ?: error("Cannot open this file")
                content = bytes.toString(Charsets.UTF_8)
                name = context.contentResolver.query(
                    uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null,
                )?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                } ?: "opened-file.txt"
                preview = false
                status = "Loaded $name; original remains unchanged"
            }.onFailure { status = it.message ?: "Unable to open file" }
        }
    }
    val save = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain"),
    ) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                val bytes = content.toByteArray(Charsets.UTF_8)
                require(bytes.size <= maxBytes) { "File exceeds 256 KB" }
                context.contentResolver.openOutputStream(uri, "wt")?.use { it.write(bytes) }
                    ?: error("Cannot write selected destination")
                status = "Saved a new copy. Source file was not overwritten."
            }.onFailure { status = it.message ?: "Unable to save file" }
        }
    }

    MaterialTheme {
        Scaffold(topBar = { TopAppBar(title = { Text("Mobile Harness • Moto Lite") }) }) { padding ->
            Column(
                Modifier.fillMaxSize().padding(padding).padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Offline file editor / HTML preview • no root or ADB", style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { open.launch(arrayOf("text/*", "application/json", "application/xml", "*/*")) }) {
                        Text("Open")
                    }
                    Button(onClick = { save.launch(name.ifBlank { "new-file.txt" }) }) {
                        Text("Save copy")
                    }
                    OutlinedButton(onClick = { preview = !preview }, enabled = name.endsWith(".html", true) || content.trimStart().startsWith("<!doctype html", true) }) {
                        Text(if (preview) "Editor" else "HTML preview")
                    }
                }
                Text(name, style = MaterialTheme.typography.labelMedium)
                if (preview) {
                    AndroidView(
                        factory = { ctx -> WebView(ctx).apply {
                            settings.javaScriptEnabled = false
                            settings.blockNetworkLoads = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                        } },
                        update = { view -> view.loadDataWithBaseURL(null, content, "text/html", "UTF-8", null) },
                        modifier = Modifier.fillMaxWidth().weight(1f),
                        onRelease = { it.destroy() },
                    )
                } else {
                    OutlinedTextField(
                        value = content,
                        onValueChange = { next ->
                            if (next.toByteArray(Charsets.UTF_8).size <= maxBytes) content = next
                            else status = "256 KB file-size limit reached"
                        },
                        label = { Text("Code / text") },
                        modifier = Modifier.fillMaxWidth().weight(1f),
                        singleLine = false,
                        maxLines = Int.MAX_VALUE,
                    )
                }
                Text(status, style = MaterialTheme.typography.bodySmall)
                Text("Linux shell, Claude Code, APK builds and PRoot require an ARM64 userspace and are NOT enabled in this mode.",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}