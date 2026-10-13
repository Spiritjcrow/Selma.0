package ai.selma.somagram;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.drinkless.tdlib.Client;
import org.drinkless.tdlib.TdApi;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Owner-operated Telegram user login with read-only chat-title listing.
 * No message read/send/delete/forward methods or background automation.
 */
public final class MainActivity extends Activity {
    private TextView status;
    private TextView results;
    private EditText appIdInput;
    private EditText appHashInput;
    private EditText phoneInput;
    private EditText codeInput;
    private EditText passwordInput;

    private Client client;
    private TdApi.AuthorizationState authorizationState;
    private int appId;
    private String appHash;
    private final AtomicInteger chatRepliesPending = new AtomicInteger();
    private final List<String> chatTitles = new ArrayList<>();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        setStatus("Somagram is not connected. Enter your Telegram application ID and hash on this phone.");
    }

    private EditText input(LinearLayout root, String hint, int type) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setSingleLine(true);
        field.setInputType(type);
        root.addView(field);
        return field;
    }

    private void button(LinearLayout root, String label, View.OnClickListener action) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(action);
        root.addView(button);
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (18f * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Somagram · SelmaOS");
        title.setTextSize(24);
        root.addView(title);

        TextView explanation = new TextView(this);
        explanation.setText("Private Android account login. This version only identifies the account and lists up to five chat titles. It does not read or send messages.");
        root.addView(explanation);

        appIdInput = input(root, "Application API ID (number)", InputType.TYPE_CLASS_NUMBER);
        appHashInput = input(root, "Application API hash (not bot token)",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        phoneInput = input(root, "Telegram phone number (+country code)", InputType.TYPE_CLASS_PHONE);
        codeInput = input(root, "Telegram login code", InputType.TYPE_CLASS_TEXT);
        passwordInput = input(root, "Two-step verification password",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);

        button(root, "Connect / begin account login", view -> beginLogin());
        button(root, "Submit phone number", view -> submitPhone());
        button(root, "Submit login code", view -> submitCode());
        button(root, "Submit two-step password", view -> submitPassword());
        button(root, "Show five chat titles (read-only)", view -> listChats());

        status = new TextView(this);
        status.setTextSize(16);
        status.setPadding(0, pad, 0, pad);
        root.addView(status);
        results = new TextView(this);
        results.setTextSize(15);
        root.addView(results);
        setContentView(scroll);
    }

    private void setStatus(String message) {
        runOnUiThread(() -> {
            if (status != null) status.setText(message);
        });
    }

    private void setResults(String message) {
        runOnUiThread(() -> {
            if (results != null) results.setText(message);
        });
    }

    private void beginLogin() {
        if (client != null) {
            setStatus("Session already started. Follow the login prompt below.");
            return;
        }
        try {
            appId = Integer.parseInt(appIdInput.getText().toString().trim());
            if (appId <= 0) throw new IllegalArgumentException("Invalid API ID");
            appHash = appHashInput.getText().toString().trim();
            if (!appHash.matches("[a-fA-F0-9]{32}")) {
                setStatus("Enter the 32-character application API hash from my.telegram.org, not your bot token.");
                return;
            }
            // TDLib drives login via authorization-state updates, not browser redirects.
            client = Client.create(this::onUpdate,
                    error -> setStatus("Telegram update error; check app configuration."),
                    error -> setStatus("Telegram request failed."));
            setStatus("Connecting to Telegram; authorization prompts will appear below.");
        } catch (NumberFormatException exc) {
            setStatus("Enter a valid numeric application API ID.");
        } catch (UnsatisfiedLinkError exc) {
            client = null;
            setStatus("TDLib native library missing for this phone; APK requires a compatible TDLib Android build.");
        } catch (RuntimeException exc) {
            client = null;
            setStatus("Could not start Telegram login. Check local configuration.");
        }
    }

    private void onUpdate(TdApi.Object update) {
        if (update instanceof TdApi.UpdateAuthorizationState) {
            onAuthorizationState(((TdApi.UpdateAuthorizationState) update).authorizationState);
        }
    }

    private void onAuthorizationState(TdApi.AuthorizationState state) {
        authorizationState = state;
        if (state instanceof TdApi.AuthorizationStateWaitTdlibParameters) {
            try {
                File root = new File(getNoBackupFilesDir(), "somagram_tdlib");
                File db = new File(root, "database");
                File files = new File(root, "files");
                if (!db.isDirectory() && !db.mkdirs()) throw new IllegalStateException("Database directory unavailable");
                if (!files.isDirectory() && !files.mkdirs()) throw new IllegalStateException("Files directory unavailable");
                TdApi.SetTdlibParameters params = new TdApi.SetTdlibParameters();
                params.useTestDc = false;
                params.databaseDirectory = db.getAbsolutePath();
                params.filesDirectory = files.getAbsolutePath();
                params.databaseEncryptionKey = SessionKeyStore.loadOrCreate(this);
                params.useFileDatabase = true;
                params.useChatInfoDatabase = true;
                params.useMessageDatabase = false;
                params.useSecretChats = false;
                params.apiId = appId;
                params.apiHash = appHash;
                params.systemLanguageCode = "en";
                params.deviceModel = "Android";
                params.systemVersion = Build.VERSION.RELEASE;
                params.applicationVersion = "Somagram 0.1.0";
                client.send(params, this::handleResult);
                // No credential is intentionally saved in SharedPreferences.
                runOnUiThread(() -> appHashInput.setText(""));
                appHash = null;
                setStatus("Initializing local encrypted Telegram session...");
            } catch (Exception exc) {
                setStatus("Could not initialize secure local Telegram database.");
            }
        } else if (state instanceof TdApi.AuthorizationStateWaitPhoneNumber) {
            setStatus("Enter your Telegram phone number with country code, then tap Submit phone number.");
        } else if (state instanceof TdApi.AuthorizationStateWaitCode) {
            setStatus("Enter the Telegram login code on this device; never share it with ChatGPT.");
        } else if (state instanceof TdApi.AuthorizationStateWaitPassword) {
            setStatus("Enter your Telegram two-step verification password on this device.");
        } else if (state instanceof TdApi.AuthorizationStateWaitOtherDeviceConfirmation) {
            setStatus("Telegram requires approval on another signed-in device. Open Telegram there to approve.");
        } else if (state instanceof TdApi.AuthorizationStateReady) {
            setStatus("Account authorized. Only read-only identity and chat-title listing are enabled.");
            client.send(new TdApi.GetMe(), result -> {
                if (result instanceof TdApi.User) {
                    TdApi.User user = (TdApi.User) result;
                    setResults("Logged in as " + user.firstName + " (Telegram ID " + user.id + ").");
                } else handleResult(result);
            });
        } else if (state instanceof TdApi.AuthorizationStateWaitEmailAddress
                || state instanceof TdApi.AuthorizationStateWaitEmailCode
                || state instanceof TdApi.AuthorizationStateWaitRegistration) {
            setStatus("This account requires an additional Telegram authorization step not yet supported in this preview. No account changes were made.");
        } else {
            setStatus("Telegram authorization state: " + state.getClass().getSimpleName());
        }
    }

    private boolean isState(Class<? extends TdApi.AuthorizationState> expected, String action) {
        if (client != null && expected.isInstance(authorizationState)) return true;
        setStatus(action + " is unavailable at the current authorization step.");
        return false;
    }

    private void submitPhone() {
        if (!isState(TdApi.AuthorizationStateWaitPhoneNumber.class, "Phone login")) return;
        String phone = phoneInput.getText().toString().trim();
        if (!phone.matches("\\+[0-9]{7,15}")) {
            setStatus("Use a phone number like +1 followed by the digits.");
            return;
        }
        client.send(new TdApi.SetAuthenticationPhoneNumber(phone, null), this::handleResult);
        phoneInput.setText("");
    }

    private void submitCode() {
        if (!isState(TdApi.AuthorizationStateWaitCode.class, "Login code")) return;
        String code = codeInput.getText().toString().trim();
        if (code.isEmpty()) return;
        client.send(new TdApi.CheckAuthenticationCode(code), this::handleResult);
        codeInput.setText("");
    }

    private void submitPassword() {
        if (!isState(TdApi.AuthorizationStateWaitPassword.class, "Two-step password")) return;
        String password = passwordInput.getText().toString();
        if (password.isEmpty()) return;
        client.send(new TdApi.CheckAuthenticationPassword(password), this::handleResult);
        passwordInput.setText("");
    }

    private void handleResult(TdApi.Object result) {
        if (result instanceof TdApi.Error) {
            TdApi.Error error = (TdApi.Error) result;
            // TDLib errors do not need to expose any user secret.
            setStatus("Telegram rejected the step (code " + error.code + "). Check the credentials or authorization prompt.");
        }
    }

    private void listChats() {
        if (!isState(TdApi.AuthorizationStateReady.class, "Chat list")) return;
        setStatus("Loading up to five chat titles; no chat messages are requested.");
        // loadChats maintains TDLib's local chat list. getChats only returns IDs.
        client.send(new TdApi.LoadChats(new TdApi.ChatListMain(), 5), ignored ->
            client.send(new TdApi.GetChats(new TdApi.ChatListMain(), 5), result -> {
                if (!(result instanceof TdApi.Chats)) {
                    handleResult(result);
                    return;
                }
                long[] ids = ((TdApi.Chats) result).chatIds;
                synchronized (chatTitles) {
                    chatTitles.clear();
                    chatRepliesPending.set(Math.min(ids.length, 5));
                }
                if (chatRepliesPending.get() == 0) {
                    setResults("No chat titles available yet.");
                    return;
                }
                for (int index = 0; index < Math.min(ids.length, 5); index++) {
                    client.send(new TdApi.GetChat(ids[index]), chat -> {
                        synchronized (chatTitles) {
                            if (chat instanceof TdApi.Chat) {
                                chatTitles.add(((TdApi.Chat) chat).title);
                            } else {
                                chatTitles.add("(title unavailable)");
                            }
                            if (chatRepliesPending.decrementAndGet() == 0) {
                                setResults("Chat titles only:\n" + String.join("\n", chatTitles));
                                setStatus("Read-only list complete. No Telegram messages were read.");
                            }
                        }
                    });
                }
            })
        );
    }

    @Override protected void onDestroy() {
        if (client != null) {
            client.send(new TdApi.Close(), ignored -> {});
            client = null;
        }
        super.onDestroy();
    }
}
