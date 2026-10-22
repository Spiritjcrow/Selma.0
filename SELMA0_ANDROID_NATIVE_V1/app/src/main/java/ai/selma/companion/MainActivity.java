package ai.selma.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public final class MainActivity extends Activity {
    private static final String SELMA_URL =
            "https://selma-official-companion.spiritjcrow1990.chatgpt.site";
    private static final String SELMA_HOST =
            "selma-official-companion.spiritjcrow1990.chatgpt.site";
    private WebView webView;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        showChooser();
    }

    private int dp(int pixels) {
        return (int) (pixels * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void showChooser() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }

        LinearLayout root = new LinearLayout(this);
        root.setBackgroundColor(Color.rgb(17, 19, 27));
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(22), dp(22), dp(22), dp(22));
        root.setOrientation(LinearLayout.VERTICAL);

        TextView title = new TextView(this);
        title.setText("SELMA.0");
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        title.setTextColor(Color.WHITE);
        root.addView(title);

        TextView description = new TextView(this);
        description.setText("Choose how Selma connects.\n" +
                "Local requires the Selma Termux service running on this phone.");
        description.setTextSize(15);
        description.setTextColor(Color.LTGRAY);
        description.setGravity(Gravity.CENTER);
        description.setPadding(0, dp(16), 0, dp(24));
        root.addView(description);

        Button local = new Button(this);
        local.setText("Local Selma + Avatar");
        local.setOnClickListener(v -> startActivity(
                new Intent(this, LocalAgentActivity.class)));
        root.addView(local, new LinearLayout.LayoutParams(-1, -2));

        Button cloud = new Button(this);
        cloud.setText("Online Companion (HTTPS)");
        cloud.setOnClickListener(v -> openOnline());
        root.addView(cloud, new LinearLayout.LayoutParams(-1, -2));

        setContentView(root);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void openOnline() {
        webView = new WebView(this);
        setContentView(webView);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        // Keep online-mode navigation on the exact intended HTTPS host.
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(
                    WebView view, WebResourceRequest request) {
                return !request.getUrl().isHierarchical()
                        || !"https".equalsIgnoreCase(request.getUrl().getScheme())
                        || !SELMA_HOST.equalsIgnoreCase(request.getUrl().getHost());
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(request::deny);
            }
        });
        webView.loadUrl(SELMA_URL);
    }

    @Override public void onBackPressed() {
        if (webView == null) {
            super.onBackPressed();
        } else if (webView.canGoBack()) {
            webView.goBack();
        } else {
            showChooser();
        }
    }

    @Override protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
