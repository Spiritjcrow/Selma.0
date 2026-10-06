package ai.selma.companion;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public final class NativeAuthorityTest {
    @Test public void acceptsOnlyCanonicalAdultModeDocument() {
        assertTrue(NativeAuthority.isCanonicalDocument("http://127.0.0.1:8765/adult-mode"));
        assertFalse(NativeAuthority.isCanonicalDocument("http://127.0.0.1:9999/adult-mode"));
        assertFalse(NativeAuthority.isCanonicalDocument("http://127.0.0.1:8765/other"));
        assertFalse(NativeAuthority.isCanonicalDocument("http://localhost:8765/adult-mode"));
        assertFalse(NativeAuthority.isCanonicalDocument("about:blank"));
        assertFalse(NativeAuthority.isCanonicalDocument("http://127.0.0.1:8765/adult-mode?x=1"));
    }

    @Test public void navigationRevokesOldAndRejectsStaleCommit() {
        NativeAuthority authority = new NativeAuthority();
        long first = authority.navigationStarted();
        authority.navigationCommitted(first, NativeAuthority.CANONICAL_DOCUMENT);
        assertTrue(authority.owns(first));

        long second = authority.navigationStarted();
        assertFalse(authority.owns(first));
        authority.navigationCommitted(first, NativeAuthority.CANONICAL_DOCUMENT);
        assertFalse(authority.owns(first));
        authority.navigationCommitted(second, "about:blank");
        assertFalse(authority.owns(second));
    }
}
