package io.selma.home.nativev1

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LoopbackPolicyTest {
    @Test
    fun acceptsOnlyFixedSelmaLoopbackRoutes() {
        assertTrue(LoopbackPolicy.isAllowed("http://127.0.0.1:8765/api/selma0/status/v1"))
        assertTrue(LoopbackPolicy.isAllowed("http://127.0.0.1:8765/api/selma0/chat/v1"))
    }

    @Test
    fun rejectsRemoteOrMutatedRoutes() {
        assertFalse(LoopbackPolicy.isAllowed("https://example.com/api/selma0/status/v1"))
        assertFalse(LoopbackPolicy.isAllowed("http://127.0.0.1:8765/api/selma0/memory/v1"))
        assertFalse(LoopbackPolicy.isAllowed("http://127.0.0.1:8765/api/selma0/chat/v1?redirect=1"))
        assertFalse(LoopbackPolicy.isAllowed("http://user@127.0.0.1:8765/api/selma0/chat/v1"))
    }
}
