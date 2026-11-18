package ai.selma.somagram;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyStore;
import java.security.SecureRandom;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * App-private Android Keystore wrapping for TDLib's 32-byte database key.
 * The session is in no-backup internal storage and is never exported.
 */
public final class SessionKeyStore {
    private static final String ALIAS = "somagram_tdlib_key_wrap_v1";
    private static final String PREF = "somagram_session_wrap_v1";
    private static final String KEY_IV = "iv";
    private static final String KEY_DATA = "ciphertext";

    private SessionKeyStore() {}

    private static SecretKey wrappingKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(
                    ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }

    public static byte[] loadOrCreate(Context context) throws Exception {
        SharedPreferences preferences = context.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        String iv = preferences.getString(KEY_IV, null);
        String data = preferences.getString(KEY_DATA, null);
        SecretKey wrap = wrappingKey();
        if (iv != null || data != null) {
            if (iv == null || data == null) {
                throw new IllegalStateException("Incomplete encrypted session key");
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, wrap,
                    new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
            byte[] result = cipher.doFinal(Base64.decode(data, Base64.NO_WRAP));
            if (result.length != 32) throw new IllegalStateException("Invalid session key");
            return result;
        }
        byte[] result = new byte[32];
        new SecureRandom().nextBytes(result);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, wrap);
        byte[] encrypted = cipher.doFinal(result);
        if (!preferences.edit()
                .putString(KEY_IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString(KEY_DATA, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .commit()) {
            throw new IllegalStateException("Could not persist encrypted session key");
        }
        return result;
    }
}
