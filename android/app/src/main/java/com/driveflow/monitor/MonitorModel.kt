package com.driveflow.monitor

import java.util.Locale

object MonitorModel {
    val statuses = mapOf("idle" to "Disponível", "preparing" to "Preparando", "uploading" to "Enviando",
        "paused" to "Pausado", "completed" to "Concluído", "error" to "Erro", "offline" to "Desconectado")
    fun bytes(value: Double): String {
        if (!value.isFinite() || value <= 0) return "0 B"
        var n = value
        val units = listOf("B", "KiB", "MiB", "GiB", "TiB")
        var i = 0
        while (n >= 1024 && i < units.lastIndex) { n /= 1024; i++ }
        return String.format(Locale.forLanguageTag("pt-BR"), "%.1f %s", n, units[i])
    }
    fun duration(seconds: Double?): String = when {
        seconds == null || !seconds.isFinite() || seconds < 0 -> "Calculando…"
        seconds >= 3600 -> "${(seconds / 3600).toInt()} h ${((seconds % 3600) / 60).toInt()} min"
        seconds >= 60 -> "${(seconds / 60).toInt()} min"
        else -> "${seconds.toInt()} s"
    }
    fun stale(status: String, lastUpdate: Long?, now: Long, intervalSeconds: Double = 5.0): Boolean =
        status in listOf("uploading", "preparing") &&
            (lastUpdate == null || now - lastUpdate > maxOf(90000.0, intervalSeconds.coerceIn(1.0, 3600.0) * 3000))
    fun validToken(token: String) = Regex("^[A-Za-z0-9_-]{43}$").matches(token)
}
