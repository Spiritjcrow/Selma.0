package io.selma.home.nativev1

import java.net.URI

object LoopbackPolicy {
    const val BASE_URL = "http://127.0.0.1:8765"

    private val allowedPaths = setOf(
        "/api/selma0/status/v1",
        "/api/selma0/chat/v1",
    )

    fun urlFor(path: String): String {
        require(path in allowedPaths) { "Selma endpoint is not allowlisted" }
        return BASE_URL + path
    }

    fun isAllowed(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme == "http" &&
            uri.host == "127.0.0.1" &&
            uri.port == 8765 &&
            uri.rawUserInfo == null &&
            uri.rawQuery == null &&
            uri.rawFragment == null &&
            uri.path in allowedPaths
    }.getOrDefault(false)
}
