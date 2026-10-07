package ai.selma.companion;

import java.net.URI;

/** Document-scoped authority and local resource boundary for the privileged WebView. */
final class NativeAuthority {
    static final String CANONICAL_DOCUMENT = "http://127.0.0.1:8765/adult-mode";

    private long generation;
    private boolean trusted;

    synchronized long navigationStarted() {
        trusted = false;
        return ++generation;
    }

    synchronized void navigationCommitted(long candidateGeneration, String url) {
        trusted = candidateGeneration == generation && isCanonicalDocument(url);
    }

    synchronized long activeGeneration() {
        return trusted ? generation : -1L;
    }

    synchronized long candidateGeneration() {
        return generation;
    }

    synchronized boolean owns(long candidateGeneration) {
        return trusted && candidateGeneration == generation;
    }

    synchronized void revoke() {
        trusted = false;
        generation++;
    }

    static boolean isCanonicalDocument(String value) {
        if (value == null) return false;
        try {
            URI uri = URI.create(value);
            return "http".equalsIgnoreCase(uri.getScheme())
                && "127.0.0.1".equals(uri.getHost())
                && uri.getPort() == 8765
                && "/adult-mode".equals(uri.getRawPath())
                && uri.getRawQuery() == null
                && uri.getRawFragment() == null
                && uri.getRawUserInfo() == null;
        } catch (IllegalArgumentException ignored) {
            return false;
        }
    }

    static boolean isAllowedResource(String value) {
        if (value == null) return false;
        try {
            URI uri = URI.create(value);
            if ("about".equalsIgnoreCase(uri.getScheme())) {
                return "about:blank".equalsIgnoreCase(value);
            }
            return "http".equalsIgnoreCase(uri.getScheme())
                && "127.0.0.1".equals(uri.getHost())
                && uri.getPort() == 8765
                && uri.getRawUserInfo() == null;
        } catch (IllegalArgumentException ignored) {
            return false;
        }
    }
}
