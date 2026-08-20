package io.selma.home.nativev1

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class SelmaRuntimeClient {
    fun status(): Result<String> = request(
        method = "GET",
        path = "/api/selma0/status/v1",
        body = null,
    )

    fun chat(message: String): Result<String> {
        val clean = message.trim()
        require(clean.isNotEmpty()) { "Message is empty" }
        require(clean.length <= 16_000) { "Message is too large" }

        val body = JSONObject().put("message", clean).toString()
        return request("POST", "/api/selma0/chat/v1", body).map { raw ->
            val response = JSONObject(raw)
            response.optString("text").ifBlank { raw }
        }
    }

    private fun request(method: String, path: String, body: String?): Result<String> = runCatching {
        val endpoint = LoopbackPolicy.urlFor(path)
        check(LoopbackPolicy.isAllowed(endpoint)) { "Blocked non-loopback endpoint" }

        val connection = URL(endpoint).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 2_500
            connection.readTimeout = 45_000
            connection.useCaches = false
            connection.setRequestProperty("Accept", "application/json")

            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { output ->
                    output.write(body.toByteArray(Charsets.UTF_8))
                }
            }

            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            check(text.length <= 256_000) { "Selma response exceeded the local safety limit" }
            check(code in 200..299) { "Local Selma returned HTTP $code: $text" }
            text
        } finally {
            connection.disconnect()
        }
    }
}
