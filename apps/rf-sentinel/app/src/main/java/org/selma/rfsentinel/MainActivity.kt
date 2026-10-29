package org.selma.rfsentinel

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Foreground-only, manually initiated aggregate radio survey.
 * Radio readings are NOT a detector for humans, vital signs, thoughts or threats.
 */
class MainActivity : Activity() {
    private var wifiManager: WifiManager? = null
    private lateinit var summary: TextView
    private lateinit var details: TextView
    private val handler = Handler(Looper.getMainLooper())
    private val bleSamples = mutableMapOf<Int, Int>() // Ephemeral per-scan deduplication; not exported.
    private var scanner: BluetoothLeScanner? = null
    private var scanningBle = false
    private var pendingAction: (() -> Unit)? = null
    private var activityStarted = false
    private var wifiCount: Int? = null
    private var wifiMean: Double? = null
    private var bleCount: Int? = null
    private var bleMean: Double? = null
    private var wifiAge = "Wi-Fi: no scan yet"
    private var bleStatus = "BLE: no scan yet"
    private var notice = "No sensing runs without a user action and the required permission."
    private var baseline: SignalSnapshot? = null

    private data class Row(
        val timestamp: Long, val wifiCount: Int?, val wifiMean: Double?,
        val bleCount: Int?, val bleMean: Double?, val score: Int?
    )
    private val rows = mutableListOf<Row>()
    private val stopTask = Runnable { stopBle() }

    private val wifiReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (!activityStarted) return
            if (intent?.action == WifiManager.SCAN_RESULTS_AVAILABLE_ACTION) {
                readWifi(intent.getBooleanExtra(WifiManager.EXTRA_RESULTS_UPDATED, false))
            }
        }
    }
    private val bleCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            if (scanningBle) bleSamples[result.device.hashCode()] = result.rssi
        }
        override fun onBatchScanResults(results: MutableList<ScanResult>) {
            if (scanningBle) {
                for (result in results) bleSamples[result.device.hashCode()] = result.rssi
            }
        }
        override fun onScanFailed(errorCode: Int) {
            if (!activityStarted || !scanningBle) return
            scanningBle = false
            handler.removeCallbacks(stopTask)
            scanner = null
            notice = "BLE scan failed, Android error code " + errorCode
            render()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 32, 28, 28)
        }
        val heading = TextView(this).apply {
            text = "SELMA RF SENTINEL | source alpha"
            textSize = 23f
        }
        val disclaimer = TextView(this).apply {
            text = "Wi-Fi access points and BLE radios are not people, pets, heartbeats, speech or threats."
            textSize = 15f
        }
        summary = TextView(this).apply { textSize = 20f }
        details = TextView(this).apply { textSize = 14f }
        panel.addView(heading)
        panel.addView(disclaimer)
        panel.addView(summary)
        panel.addView(details)
        fun button(label: String, action: () -> Unit) {
            panel.addView(Button(this).apply {
                text = label
                setOnClickListener { action() }
            }, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ))
        }
        button("SCAN WI-FI ONCE") {
            withPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)) { startWifi() }
        }
        button("SCAN BLE (12 SECONDS)") {
            val permissions = if (Build.VERSION.SDK_INT >= 31)
                arrayOf(Manifest.permission.BLUETOOTH_SCAN)
            else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
            withPermissions(permissions) { startBle() }
        }
        button("STOP BLE SCAN") { stopBle() }
        button("SAVE CURRENT READING AS BASELINE") {
            baseline = snapshot()
            notice = if (baseline == null) "Scan Wi-Fi and BLE first." else "Baseline set in RAM."
            render()
        }
        button("EXPORT CSV") { exportCsv() }
        setContentView(ScrollView(this).apply { addView(panel) })
        registerReceiver(wifiReceiver, IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION))
        render()
    }

    override fun onStart() {
        super.onStart()
        activityStarted = true
    }

    private fun withPermissions(permissions: Array<String>, action: () -> Unit) {
        val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isEmpty()) action()
        else {
            pendingAction = action
            requestPermissions(missing.toTypedArray(), 901)
        }
    }
    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 901) {
            val action = pendingAction
            pendingAction = null
            if (!activityStarted) {
                notice = "Permission result ignored while app is not visible."
                render()
                return
            }
            if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED })
                action?.invoke()
            else {
                notice = "Permission declined; scanning disabled."
                render()
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun startWifi() {
        val manager = wifiManager
        if (manager == null) {
            notice = "Wi-Fi hardware unavailable."
            render()
            return
        }
        try {
            val started = manager.startScan()
            notice = if (started) "Wi-Fi scan requested." else
                "Wi-Fi scan unavailable or throttled; results may be cached."
            readWifi(false)
        } catch (_: SecurityException) {
            notice = "Wi-Fi needs Location permission and Location services enabled."
            render()
        } catch (exc: Exception) {
            notice = "Wi-Fi scan unavailable: " + exc.javaClass.simpleName
            render()
        }
    }

    @Suppress("DEPRECATION")
    private fun readWifi(fresh: Boolean) {
        if (!activityStarted) {
            notice = "Wi-Fi result ignored while app is not visible."
            return
        }
        val manager = wifiManager
        if (manager == null) {
            notice = "Wi-Fi hardware unavailable."
            render()
            return
        }
        try {
            val results = manager.scanResults
            wifiCount = results.size
            wifiMean = results.map { it.level.toDouble() }.average().takeIf { !it.isNaN() }
            val timestampUs = results.maxOfOrNull { it.timestamp }
            val seconds = timestampUs?.let {
                ((SystemClock.elapsedRealtimeNanos() / 1000L - it).coerceAtLeast(0L) / 1000000L)
            }
            wifiAge = "Wi-Fi result " + (if (fresh) "updated" else "may be cached") +
                "; newest AP approximately " + (seconds?.toString() ?: "unknown") + " seconds old."
            saveRow()
        } catch (_: SecurityException) {
            notice = "Wi-Fi results blocked by Android Location settings."
        } catch (exc: Exception) {
            notice = "Wi-Fi read failed: " + exc.javaClass.simpleName
        }
        render()
    }

    private fun startBle() {
        stopBle()
        bleSamples.clear()
        try {
            scanner = getSystemService(BluetoothManager::class.java)?.adapter?.bluetoothLeScanner
            val active = scanner
            if (active == null) {
                notice = "BLE unavailable or Bluetooth switched off."
                render()
                return
            }
            scanningBle = true
            active.startScan(
                null,
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_POWER).build(),
                bleCallback
            )
            handler.postDelayed(stopTask, 12000L)
            notice = "BLE advertisement survey running for 12 seconds."
            render()
        } catch (_: SecurityException) {
            scanningBle = false
            notice = "BLE scan blocked by Android permissions."
            render()
        } catch (exc: Exception) {
            scanningBle = false
            notice = "BLE scan unavailable: " + exc.javaClass.simpleName
            render()
        }
    }

    private fun stopBle(recordResults: Boolean = true) {
        handler.removeCallbacks(stopTask)
        if (!scanningBle) return
        scanningBle = false
        try { scanner?.stopScan(bleCallback) } catch (_: Exception) {}
        scanner = null
        if (!recordResults) {
            bleSamples.clear()
            notice = "BLE scan stopped when app left the foreground; partial result discarded."
            return
        }
        bleCount = bleSamples.size
        bleMean = bleSamples.values.map { it.toDouble() }.average().takeIf { !it.isNaN() }
        bleStatus = "BLE: " + bleCount + " distinct radio devices this scan, not people."
        notice = "BLE scan stopped."
        saveRow()
        render()
    }

    private fun snapshot(): SignalSnapshot? {
        return SignalSnapshot(wifiCount ?: return null, wifiMean,
            bleCount ?: return null, bleMean)
    }
    private fun score(): Int? {
        val ref = baseline ?: return null
        val current = snapshot() ?: return null
        return RfMetrics.variability(ref, current)
    }
    private fun saveRow() {
        rows.add(Row(System.currentTimeMillis(), wifiCount, wifiMean, bleCount, bleMean, score()))
        if (rows.size > 250) rows.removeAt(0)
    }
    private fun render() {
        if (!::summary.isInitialized) return
        summary.text = "Wi-Fi AP count: " + (wifiCount?.toString() ?: "not measured") +
            "\nBLE radio count: " + (bleCount?.toString() ?: "not measured") +
            "\nRF change index (0-100): " + (score()?.toString() ?: "not calibrated")
        details.text = "\nWi-Fi mean RSSI: " + (wifiMean?.toString() ?: "unknown") +
            "\nBLE mean RSSI: " + (bleMean?.toString() ?: "unknown") +
            "\n" + wifiAge + "\n" + bleStatus +
            "\nBLE active: " + scanningBle +
            "\nStatus: " + notice +
            "\n\nReadings are environmental radio observations ONLY. " +
            "They cannot measure thoughts, conversations, heartbeats or attack intentions."
    }
    private fun exportCsv() {
        if (rows.isEmpty()) {
            notice = "Nothing to export; scan first."
            render()
            return
        }
        @Suppress("DEPRECATION")
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "text/csv"
            putExtra(Intent.EXTRA_TITLE, "selma_rf_aggregate.csv")
        }
        @Suppress("DEPRECATION")
        startActivityForResult(intent, 902)
    }

    @Deprecated("Simple local export without external dependencies")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 902 || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        try {
            val stream = contentResolver.openOutputStream(uri)
                ?: throw java.io.IOException("No document output stream")
            stream.bufferedWriter().use { writer ->
                writer.appendLine("timestamp,wifi_ap_count,wifi_mean_rssi_dbm,ble_radio_count,ble_mean_rssi_dbm,rf_change_index")
                val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssZ", Locale.US)
                for (row in rows) {
                    writer.appendLine(listOf(
                        dateFormat.format(Date(row.timestamp)),
                        row.wifiCount ?: "", row.wifiMean ?: "",
                        row.bleCount ?: "", row.bleMean ?: "", row.score ?: ""
                    ).joinToString(","))
                }
            }
            notice = "Aggregate CSV exported; no device identifiers, MACs or SSIDs."
        } catch (exc: Exception) {
            notice = "Export failed: " + exc.javaClass.simpleName
        }
        render()
    }

    override fun onStop() {
        activityStarted = false
        pendingAction = null
        stopBle(recordResults = false) // Never retain a partial scan from background transition.
        super.onStop()
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        unregisterReceiver(wifiReceiver)
        super.onDestroy()
    }
}

