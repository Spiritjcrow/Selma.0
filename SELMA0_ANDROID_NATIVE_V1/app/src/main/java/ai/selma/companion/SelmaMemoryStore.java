package ai.selma.companion;

import org.json.JSONObject;
import org.json.JSONException;

/**
 * Native persistent memory operations backed by Android Keystore encryption.
 * This class is intentionally not exposed to untrusted WebView JavaScript.
 */
public final class SelmaMemoryStore {
    private static final String PREFIX = "memory.v1.";
    private final EncryptedLocalStore encrypted;

    public SelmaMemoryStore(EncryptedLocalStore encrypted) {
        if (encrypted == null) throw new IllegalArgumentException("encrypted store required");
        this.encrypted = encrypted;
    }

    public void save(String id, String text) throws Exception {
        validateId(id);
        if (text == null) throw new IllegalArgumentException("memory text required");
        JSONObject record = new JSONObject();
        record.put("id", id);
        record.put("text", text);
        record.put("updated_at_ms", System.currentTimeMillis());
        encrypted.put(PREFIX + id, record.toString());
    }

    public String read(String id) throws Exception {
        validateId(id);
        String raw = encrypted.get(PREFIX + id);
        if (raw == null) return null;
        JSONObject record = new JSONObject(raw);
        if (!id.equals(record.getString("id"))) {
            throw new SecurityException("Memory identifier mismatch");
        }
        return record.getString("text");
    }

    public void delete(String id) {
        validateId(id);
        encrypted.remove(PREFIX + id);
    }

    private static void validateId(String id) {
        if (id == null || !id.matches("[A-Za-z0-9_-]{1,128}")) {
            throw new IllegalArgumentException("Invalid memory identifier");
        }
    }
}
