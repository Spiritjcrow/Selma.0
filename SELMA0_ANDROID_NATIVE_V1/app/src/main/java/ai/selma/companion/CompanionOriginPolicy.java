package ai.selma.companion;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Allow only HTTPS navigation to the exact configured Selma companion origin. */
public final class CompanionOriginPolicy {
    private static final String TRUSTED_HOST = "selma-official-companion.spiritjcrow1990.chatgpt.site";

    private CompanionOriginPolicy() {}

    public static boolean isTrusted(String destination) {
        if (destination == null || destination.isEmpty()) return false;
        try {
            URI uri = new URI(destination);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null) return false;
            if (uri.getRawUserInfo() != null) return false;
            if (uri.getPort() != -1 && uri.getPort() != 443) return false;
            return TRUSTED_HOST.equals(host.toLowerCase(Locale.ROOT));
        } catch (URISyntaxException | IllegalArgumentException exception) {
            return false;
        }
    }
}
