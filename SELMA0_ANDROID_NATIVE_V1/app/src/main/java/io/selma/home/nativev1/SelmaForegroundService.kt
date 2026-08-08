package io.selma.home.nativev1

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat

class SelmaForegroundService : Service() {
    private lateinit var overlayController: OverlayController

    override fun onCreate() {
        super.onCreate()
        overlayController = OverlayController(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startVisibleService()
        when (intent?.action ?: ACTION_START) {
            ACTION_SHOW -> overlayController.show()
            ACTION_HIDE -> overlayController.hide()
            ACTION_STOP -> {
                overlayController.hide()
                ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
                stopSelf()
                return START_NOT_STICKY
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        overlayController.hide()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startVisibleService() {
        val openApp = PendingIntent.getActivity(
            this,
            1,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val summon = PendingIntent.getService(
            this,
            2,
            actionIntent(this, ACTION_SHOW),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stop = PendingIntent.getService(
            this,
            3,
            actionIntent(this, ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_selma)
            .setContentTitle("Selma.0 is available")
            .setContentText("Device-local assistant service. Tap to open.")
            .setContentIntent(openApp)
            .setOngoing(true)
            .setSilent(true)
            .addAction(R.drawable.ic_selma, "Summon", summon)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", stop)
            .build()

        val serviceType = if (Build.VERSION.SDK_INT >= 34) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        } else {
            0
        }
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, serviceType)
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                getString(R.string.service_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = getString(R.string.service_channel_description)
                setShowBadge(false)
            },
        )
    }

    companion object {
        const val ACTION_START = "io.selma.home.nativev1.action.START"
        const val ACTION_SHOW = "io.selma.home.nativev1.action.SHOW"
        const val ACTION_HIDE = "io.selma.home.nativev1.action.HIDE"
        const val ACTION_STOP = "io.selma.home.nativev1.action.STOP"

        private const val CHANNEL_ID = "selma0_active_v1"
        private const val NOTIFICATION_ID = 4100

        fun actionIntent(context: Context, action: String): Intent =
            Intent(context, SelmaForegroundService::class.java).setAction(action)
    }
}
