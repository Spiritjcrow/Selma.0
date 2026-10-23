package org.selma.rfsentinel

import kotlin.math.abs
import kotlin.math.roundToInt

data class SignalSnapshot(
    val wifiCount: Int,
    val wifiMeanRssi: Double?,
    val bleCount: Int,
    val bleMeanRssi: Double?
)

object RfMetrics {
    // An environmental radio change index ONLY, never an estimate of personal danger.
    fun variability(baseline: SignalSnapshot, current: SignalSnapshot): Int {
        val wc = abs(current.wifiCount - baseline.wifiCount) * 10.0
        val bc = abs(current.bleCount - baseline.bleCount) * 6.0
        val wr = if (baseline.wifiMeanRssi == null || current.wifiMeanRssi == null)
            0.0 else abs(current.wifiMeanRssi - baseline.wifiMeanRssi) * 1.5
        val br = if (baseline.bleMeanRssi == null || current.bleMeanRssi == null)
            0.0 else abs(current.bleMeanRssi - baseline.bleMeanRssi)
        return (wc + bc + wr + br).coerceIn(0.0, 100.0).roundToInt()
    }
}
