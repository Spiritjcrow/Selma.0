package io.selma.home.nativev1

import android.content.Context
import android.graphics.ImageDecoder
import android.graphics.drawable.AnimatedImageDrawable
import android.widget.ImageView

class SelmaSpriteView(context: Context) : ImageView(context) {
    init {
        contentDescription = "Selma assistant. Tap to open. Drag to move."
        isClickable = true
        scaleType = ScaleType.FIT_CENTER
        val source = ImageDecoder.createSource(context.assets, MOTION_ASSET)
        setImageDrawable(ImageDecoder.decodeDrawable(source))
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        (drawable as? AnimatedImageDrawable)?.start()
    }

    override fun onDetachedFromWindow() {
        (drawable as? AnimatedImageDrawable)?.stop()
        super.onDetachedFromWindow()
    }

    companion object {
        private const val MOTION_ASSET = "selma-active-work-motion-r1.gif"
    }
}
