package com.driveflow.monitor
import org.junit.Assert.*
import org.junit.Test
class MonitorModelTest {
    @Test fun staleOnlyWhileActive() {
        assertTrue(MonitorModel.stale("uploading", 0L, 91000L))
        assertFalse(MonitorModel.stale("idle", 0L, 91000L))
        assertFalse(MonitorModel.stale("uploading", 90000L, 91000L))
        assertFalse(MonitorModel.stale("uploading", 0L, 91000L, 60.0))
    }
    @Test fun tokenRejectsPathsAndWrongLengths() {
        assertTrue(MonitorModel.validToken("a".repeat(43)))
        assertFalse(MonitorModel.validToken("../computers"))
        assertFalse(MonitorModel.validToken("a".repeat(44)))
    }
    @Test fun unitsAndUnknownDuration() {
        assertEquals("1,0 MiB", MonitorModel.bytes(1048576.0))
        assertEquals("Calculando…", MonitorModel.duration(null))
        assertEquals("1 min", MonitorModel.duration(90.0))
    }
}
