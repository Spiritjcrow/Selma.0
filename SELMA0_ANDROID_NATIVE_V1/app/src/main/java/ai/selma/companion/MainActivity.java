package ai.selma.companion;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Minimal SelmaOS home shell for Android-native devices and ChromeOS Android.
 * It has no advertising, analytics, cloud login, or third-party runtime dependency.
 */
public final class MainActivity extends Activity {
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String FDROID_PACKAGE = "org.fdroid.fdroid";
    private static final String TERMUX_URL = "https://f-droid.org/packages/com.termux/";
    private static final String FDROID_URL = "https://f-droid.org/packages/org.fdroid.fdroid/";
    private static final String STATUS_URL = "http://127.0.0.1:8765/api/selma0/status/v1";
    private static final int BACKGROUND = Color.rgb(8, 17, 31);
    private static final int PANEL = Color.rgb(17, 29, 48);
    private static final int ACCENT = Color.rgb(85, 221, 224);

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private LinearLayout appList;
    private TextView runtimeStatus;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(buildHome());
        refreshRuntimeStatus();
    }

    @Override protected void onResume() {
        super.onResume();
        populateInstalledApps();
        refreshRuntimeStatus();
    }

    @Override protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }

    private View buildHome() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BACKGROUND);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(22), dp(20), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(-1, -2));

        TextView title = text("SelmaOS", 32, Color.WHITE);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title);

        TextView subtitle = text("LOCAL-FIRST MOBILE WORKSPACE", 12, ACCENT);
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL);
        subtitle.setPadding(0, 0, 0, dp(18));
        root.addView(subtitle);

        runtimeStatus = text("Checking local runtime…", 14, Color.LTGRAY);
        runtimeStatus.setGravity(Gravity.CENTER_HORIZONTAL);
        runtimeStatus.setPadding(dp(12), dp(12), dp(12), dp(12));
        runtimeStatus.setBackgroundColor(PANEL);
        root.addView(runtimeStatus, match());

        root.addView(action("Open local Selma", v ->
                startActivity(new Intent(this, LocalAgentActivity.class))), spaced());
        root.addView(action("Refresh runtime", v -> refreshRuntimeStatus()), compact());

        root.addView(section("OPEN-SOURCE COMPONENTS"));
        root.addView(action("Termux — local runtime", v ->
                openOrInstall(TERMUX_PACKAGE, TERMUX_URL)), compact());
        root.addView(action("F-Droid — verified app catalog", v ->
                openOrInstall(FDROID_PACKAGE, FDROID_URL)), compact());

        root.addView(section("DEVICE"));
        root.addView(action("Set SelmaOS as Home", v -> openHomeSettings()), compact());

        root.addView(section("INSTALLED APPS"));
        appList = new LinearLayout(this);
        appList.setOrientation(LinearLayout.VERTICAL);
        root.addView(appList, match());
        return scroll;
    }

    private void refreshRuntimeStatus() {
        if (runtimeStatus == null || io.isShutdown()) return;
        runtimeStatus.setText("Checking local runtime…");
        io.execute(() -> {
            String message = "Runtime offline • start Selma in Termux";
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(STATUS_URL).openConnection();
                connection.setConnectTimeout(1400);
                connection.setReadTimeout(1800);
                connection.setUseCaches(false);
                if (connection.getResponseCode() == 200) {
                    JSONObject status = new JSONObject(readLimited(connection.getInputStream(), 65536));
                    boolean strict = status.optBoolean("offline_only_supported", false);
                    boolean loopback = status.optBoolean("local_llm_loopback", false);
                    message = strict && loopback
                            ? "Runtime ready • offline-only chat enforced"
                            : "Runtime found • local model configuration required";
                }
            } catch (Exception ignored) {
                // The home screen remains fully usable without the optional local runtime.
            } finally {
                if (connection != null) connection.disconnect();
            }
            final String result = message;
            runOnUiThread(() -> {
                if (!isFinishing() && runtimeStatus != null) runtimeStatus.setText(result);
            });
        });
    }

    private String readLimited(InputStream input, int limit) throws Exception {
        try (InputStream stream = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[2048];
            int count;
            while ((count = stream.read(buffer)) != -1) {
                if (output.size() + count > limit) throw new IllegalStateException("Response too large");
                output.write(buffer, 0, count);
            }
            return output.toString("UTF-8");
        }
    }

    private void populateInstalledApps() {
        if (appList == null) return;
        appList.removeAllViews();
        PackageManager manager = getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN);
        launcher.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> discovered = new ArrayList<>(manager.queryIntentActivities(launcher, 0));
        Collections.sort(discovered, (left, right) ->
                left.loadLabel(manager).toString().compareToIgnoreCase(right.loadLabel(manager).toString()));

        String previous = "";
        for (ResolveInfo info : discovered) {
            if (info.activityInfo == null || getPackageName().equals(info.activityInfo.packageName)) continue;
            String key = info.activityInfo.packageName + "/" + info.activityInfo.name;
            if (key.equals(previous)) continue;
            previous = key;
            String label = info.loadLabel(manager).toString();
            ComponentName component = new ComponentName(info.activityInfo.packageName, info.activityInfo.name);
            appList.addView(action(label, v -> launchComponent(component)), compact());
        }
        if (appList.getChildCount() == 0) {
            TextView empty = text("No launchable apps are visible.", 14, Color.LTGRAY);
            empty.setPadding(dp(4), dp(8), dp(4), dp(8));
            appList.addView(empty);
        }
    }

    private void launchComponent(ComponentName component) {
        try {
            Intent intent = new Intent(Intent.ACTION_MAIN);
            intent.addCategory(Intent.CATEGORY_LAUNCHER);
            intent.setComponent(component);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            startActivity(intent);
        } catch (Exception ignored) {
            populateInstalledApps();
        }
    }

    private void openOrInstall(String packageName, String installUrl) {
        Intent launch = getPackageManager().getLaunchIntentForPackage(packageName);
        if (launch != null) {
            startActivity(launch);
            return;
        }
        Intent web = new Intent(Intent.ACTION_VIEW, Uri.parse(installUrl));
        web.addCategory(Intent.CATEGORY_BROWSABLE);
        startActivity(web);
    }

    private void openHomeSettings() {
        try {
            startActivity(new Intent(Settings.ACTION_HOME_SETTINGS));
        } catch (Exception ignored) {
            startActivity(new Intent(Settings.ACTION_SETTINGS));
        }
    }

    private TextView section(String value) {
        TextView view = text(value, 12, ACCENT);
        view.setPadding(0, dp(24), 0, dp(8));
        return view;
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private Button action(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setAllCaps(false);
        button.setText(label);
        button.setTextSize(15);
        button.setOnClickListener(listener);
        return button;
    }

    private LinearLayout.LayoutParams match() {
        return new LinearLayout.LayoutParams(-1, -2);
    }

    private LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams params = match();
        params.setMargins(0, dp(16), 0, dp(4));
        return params;
    }

    private LinearLayout.LayoutParams compact() {
        LinearLayout.LayoutParams params = match();
        params.setMargins(0, dp(3), 0, dp(3));
        return params;
    }

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
