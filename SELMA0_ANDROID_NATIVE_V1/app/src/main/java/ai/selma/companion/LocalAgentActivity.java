package ai.selma.companion;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Permission-minimal local interface for the existing Termux Selma command core.
 * No device commands are exposed here; the user's Send tap confirms each chat turn.
 */
public final class LocalAgentActivity extends Activity {
    private static final String BASE = "http://127.0.0.1:8765";
    private static final int PURPLE = Color.rgb(145, 103, 232);
    private static final int BACKGROUND = Color.rgb(17, 19, 27);
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private TextView status;
    private TextView conversation;
    private EditText message;
    private Button send;
    private ScrollView scroll;
    private OrbView avatar;
    private volatile boolean offlineContractReady = false;

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private TextView text(String value, int size) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(Color.WHITE);
        return view;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BACKGROUND);
        root.setPadding(dp(18), dp(16), dp(18), dp(18));

        avatar = new OrbView();
        avatar.setContentDescription("Selma.0 animated twin-orb avatar");
        root.addView(avatar, new LinearLayout.LayoutParams(-1, dp(168)));

        TextView heading = text("SELMA.0  /  LOCAL", 22);
        heading.setGravity(Gravity.CENTER);
        root.addView(heading);
        status = text("Checking local connection…", 13);
        status.setTextColor(Color.LTGRAY);
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, dp(6), 0, dp(12));
        root.addView(status);

        Button refresh = new Button(this);
        refresh.setText("Check local agent");
        refresh.setOnClickListener(v -> checkStatus());
        root.addView(refresh);

        scroll = new ScrollView(this);
        conversation = text("Welcome. This screen connects to the Selma service on your phone.\n" +
                "Start the Selma Termux server to begin chatting.", 15);
        conversation.setPadding(dp(4), dp(12), dp(4), dp(12));
        scroll.addView(conversation);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        message = new EditText(this);
        message.setSingleLine(false);
        message.setMaxLines(4);
        message.setTextColor(Color.WHITE);
        message.setHintTextColor(Color.LTGRAY);
        message.setHint("Message Selma…");
        message.setBackgroundTintList(android.content.res.ColorStateList.valueOf(PURPLE));
        root.addView(message, new LinearLayout.LayoutParams(-1, -2));

        send = new Button(this);
        send.setText("Send to local Selma");
        send.setEnabled(false);
        send.setOnClickListener(v -> sendMessage());
        root.addView(send);
        setContentView(root);
        checkStatus();
    }

    private void append(String who, String content) {
        conversation.append("\n\n" + who + "\n" + content);
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private void checkStatus() {
        offlineContractReady = false;
        if (send != null) send.setEnabled(false);
        status.setText("Checking 127.0.0.1:8765…");
        io.execute(() -> {
            try {
                JSONObject result = request("GET", "/api/selma0/status/v1", null);
                final boolean supportsOffline = result.optBoolean("offline_only_supported", false);
                final boolean localEndpoint = result.optBoolean("local_llm_loopback", false);
                final boolean fallback = result.optBoolean("online_fallback_configured", false);
                runOnUiThread(() -> {
                    offlineContractReady = supportsOffline && localEndpoint;
                    send.setEnabled(offlineContractReady);
                    status.setText(offlineContractReady
                            ? (fallback
                                ? "Offline-only enforced • cloud fallback exists but is disabled here"
                                : "Offline-only bridge ready • local model required")
                            : "Offline mode blocked: update Termux agent or use a loopback model URL.");
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    offlineContractReady = false;
                    send.setEnabled(false);
                    status.setText("Local agent unavailable. Start the Selma Termux server.");
                });
            }
        });
    }

    private void sendMessage() {
        String input = message.getText().toString().trim();
        if (input.isEmpty() || !send.isEnabled() || !offlineContractReady) return;
        message.setText("");
        append("YOU", input);
        send.setEnabled(false);
        status.setText("Waiting for Selma…");
        io.execute(() -> {
            try {
                JSONObject payload = new JSONObject();
                payload.put("message", input);
                payload.put("confirmed", true); // The Send tap is per-message authorization.
                payload.put("offline_only", true); // Never use the online fallback.
                JSONObject response = request("POST", "/api/selma0/chat/v1", payload);
                if (!response.optBoolean("ok", false)) {
                    throw new IllegalStateException(response.optString("error", "Chat rejected"));
                }
                JSONObject result = response.optJSONObject("result");
                if (result == null) throw new IllegalStateException("Missing chat result");
                String answer = result.optString("text", "No model response");
                String route = result.optString("route", "unknown");
                runOnUiThread(() -> {
                    append("unavailable".equals(route) ? "SYSTEM" : "SELMA", answer);
                    status.setText("unavailable".equals(route)
                            ? "Local model unavailable; no cloud request was made"
                            : "Reply route: " + route);
                    send.setEnabled(offlineContractReady);
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    append("SYSTEM", "Could not complete the local request. Your message remains visible.");
                    status.setText("Local request failed");
                    send.setEnabled(offlineContractReady);
                });
            }
        });
    }

    /** Restrict traffic to a fixed loopback endpoint. Limit responses to 128 KiB. */
    private JSONObject request(String method, String path, JSONObject payload) throws Exception {
        URL url = new URL(BASE + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(2500);
        connection.setReadTimeout(60000);
        connection.setUseCaches(false);
        try {
            if (payload != null) {
                byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                connection.setFixedLengthStreamingMode(body.length);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(body);
                }
            }
            int code = connection.getResponseCode();
            InputStream stream = code >= 200 && code < 300
                    ? connection.getInputStream() : connection.getErrorStream();
            if (stream == null) throw new IllegalStateException("Empty response: " + code);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try (InputStream input = stream) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (out.size() + count > 131072) {
                        throw new IllegalStateException("Response too large");
                    }
                    out.write(buffer, 0, count);
                }
            }
            JSONObject result = new JSONObject(out.toString("UTF-8"));
            if (code < 200 || code >= 300) {
                throw new IllegalStateException(result.optString("error", "HTTP " + code));
            }
            return result;
        } finally {
            connection.disconnect();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (avatar != null) avatar.resume();
    }

    @Override protected void onPause() {
        if (avatar != null) avatar.pause();
        super.onPause();
    }

    @Override protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }

    /** Low-overhead 2D avatar. No GPU, AR, camera, or microphone dependency. */
    private final class OrbView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final ValueAnimator pulse = ValueAnimator.ofFloat(0f, 1f);
        private float phase = 0f;

        OrbView() {
            super(LocalAgentActivity.this);
            pulse.setDuration(2400);
            pulse.setRepeatCount(ValueAnimator.INFINITE);
            pulse.setRepeatMode(ValueAnimator.REVERSE);
            pulse.addUpdateListener(a -> {
                phase = (float) a.getAnimatedValue();
                invalidate();
            });
        }

        void resume() {
            if (!pulse.isStarted()) pulse.start();
        }

        void pause() {
            pulse.cancel();
        }

        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float cy = getHeight() / 2f;
            float cx = getWidth() / 2f;
            float radius = Math.min(getWidth() * 0.19f, getHeight() * 0.37f);
            paint.setColor(Color.rgb(76, 12, 193));
            canvas.drawCircle(cx - radius * 0.52f, cy, radius * (0.96f + phase * 0.04f), paint);
            paint.setColor(PURPLE);
            canvas.drawCircle(cx + radius * 0.52f, cy, radius * (1.03f - phase * 0.03f), paint);
        }
    }
}
