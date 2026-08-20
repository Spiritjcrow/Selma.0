package io.selma.home.nativev1

import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import kotlin.math.abs

class OverlayController(private val context: Context) {
    private val windowManager = context.getSystemService(WindowManager::class.java)
    private var overlay: View? = null

    fun show(): Boolean {
        if (!Settings.canDrawOverlays(context)) return false
        if (overlay != null) return true

        val size = (176 * context.resources.displayMetrics.density).toInt()
        val view = SelmaSpriteView(context)
        val params = WindowManager.LayoutParams(
            size,
            size * 208 / 192,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = context.resources.displayMetrics.widthPixels - size
            y = (96 * context.resources.displayMetrics.density).toInt()
        }

        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        view.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    startX = params.x
                    startY = params.y
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    params.x = startX + (event.rawX - downX).toInt()
                    params.y = startY + (event.rawY - downY).toInt()
                    windowManager.updateViewLayout(view, params)
                    true
                }
                MotionEvent.ACTION_UP -> {
                    val wasTap = abs(event.rawX - downX) < 18f && abs(event.rawY - downY) < 18f
                    if (wasTap) openSelma()
                    true
                }
                else -> false
            }
        }

        windowManager.addView(view, params)
        overlay = view
        return true
    }

    fun hide() {
        overlay?.let { view -> runCatching { windowManager.removeView(view) } }
        overlay = null
    }

    private fun openSelma() {
        context.startActivity(
            Intent(context, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            },
        )
    }
}
