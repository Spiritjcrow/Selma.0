package io.selma.home.nativev1

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {
    private val runtimeClient = SelmaRuntimeClient()
    private val executor = Executors.newSingleThreadExecutor()

    private var runtimeStatus by mutableStateOf("Not checked")
    private var responseText by mutableStateOf("Selma is ready for a device-local check.")
    private var overlayGranted by mutableStateOf(false)

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { startServiceFromVisibleActivity() }

    private val overlayPermission = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) {
        overlayGranted = Settings.canDrawOverlays(this)
        if (overlayGranted) sendServiceAction(SelmaForegroundService.ACTION_SHOW)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        overlayGranted = Settings.canDrawOverlays(this)
        setContent { SelmaScreen() }
    }

    override fun onResume() {
        super.onResume()
        overlayGranted = Settings.canDrawOverlays(this)
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    @Composable
    private fun SelmaScreen() {
        var message by rememberSaveable { mutableStateOf("") }
        val colors = darkColorScheme(
            primary = Color(0xFFD7AE54),
            secondary = Color(0xFFB47C91),
            background = Color(0xFF111218),
            surface = Color(0xFF1A1B22),
        )

        MaterialTheme(colorScheme = colors) {
            Surface(modifier = Modifier.fillMaxSize()) {
                Column(
                    modifier = Modifier
                        .verticalScroll(rememberScrollState())
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Text("Selma.0", style = MaterialTheme.typography.headlineLarge)
                    Text(
                        "Android Native V1 · rootless · Android 12+ · device-local first",
                        color = MaterialTheme.colorScheme.secondary,
                    )

                    StatusCard(runtimeStatus)

                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(onClick = ::checkRuntime) { Text("Check local core") }
                        OutlinedButton(onClick = ::startRequested) { Text("Start service") }
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(
                            onClick = ::summonRequested,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4A1024)),
                        ) {
                            Text(if (overlayGranted) "Summon Selma" else "Allow overlay")
                        }
                        OutlinedButton(onClick = { sendServiceAction(SelmaForegroundService.ACTION_HIDE) }) {
                            Text("Hide")
                        }
                        OutlinedButton(onClick = { sendServiceAction(SelmaForegroundService.ACTION_STOP) }) {
                            Text("Stop")
                        }
                    }

                    OutlinedTextField(
                        value = message,
                        onValueChange = { if (it.length <= 16_000) message = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Message local Selma") },
                        minLines = 3,
                    )
                    Button(
                        onClick = { sendMessage(message) },
                        enabled = message.isNotBlank(),
                    ) {
                        Text("Send offline-first")
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            responseText,
                            modifier = Modifier.padding(16.dp),
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }

                    Spacer(Modifier.height(12.dp))
                    Text(
                        "No root, remote server, background microphone, general shell, or hidden collection is enabled in this milestone.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }

    @Composable
    private fun StatusCard(status: String) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Local runtime", style = MaterialTheme.typography.titleMedium)
                Text(status, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }

    private fun startRequested() {
        if (
            Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            startServiceFromVisibleActivity()
        }
    }

    private fun startServiceFromVisibleActivity() {
        ContextCompat.startForegroundService(
            this,
            SelmaForegroundService.actionIntent(this, SelmaForegroundService.ACTION_START),
        )
        responseText = "Selma's visible foreground service was started by your action."
    }

    private fun summonRequested() {
        if (!Settings.canDrawOverlays(this)) {
            overlayPermission.launch(
                Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName"),
                ),
            )
            return
        }
        startRequested()
        sendServiceAction(SelmaForegroundService.ACTION_SHOW)
    }

    private fun sendServiceAction(action: String) {
        startService(
            SelmaForegroundService.actionIntent(this, action),
        )
    }

    private fun checkRuntime() {
        runtimeStatus = "Checking 127.0.0.1:8765…"
        executor.execute {
            val result = runtimeClient.status()
            runOnUiThread {
                runtimeStatus = result.fold(
                    onSuccess = { raw ->
                        val json = runCatching { JSONObject(raw) }.getOrNull()
                        val name = json?.optString("name").orEmpty().ifBlank { "Selma.0" }
                        val runtime = json?.optString("runtime").orEmpty().ifBlank { "local runtime" }
                        "$name connected · $runtime"
                    },
                    onFailure = { "Unavailable · start the Selma Termux runtime" },
                )
            }
        }
    }

    private fun sendMessage(message: String) {
        responseText = "Waiting for the device-local Selma runtime…"
        executor.execute {
            val result = runtimeClient.chat(message)
            runOnUiThread {
                responseText = result.getOrElse {
                    "Local Selma is unavailable. Start the Termux runtime; no internet fallback was attempted by this app."
                }
            }
        }
    }
}
