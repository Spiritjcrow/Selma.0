package ai.selma.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.widget.TextView;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebSettings;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public final class MainActivity extends Activity {
    private static final String SELMA_URL = "https://selma-official-companion.spiritjcrow1990.chatgpt.site";
    private static final String SELMA_HOST = "selma-official-companion.spiritjcrow1990.chatgpt.site";
    private static final int UNLOCK_REQUEST = 401;
    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        requestUnlock();
    }

    private void requestUnlock() {
        KeyguardManager manager = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (manager == null || !manager.isDeviceSecure()) {
            TextView locked = new TextView(this);
            locked.setText("Selma requires a secure device screen lock. Set a PIN, password, or pattern in Android Settings.");
            setContentView(locked);
            return;
        }
        Intent intent = manager.createConfirmDeviceCredentialIntent(
                "Unlock Selma", "Confirm device credentials to open Selma");
        if (intent == null) {
            TextView locked = new TextView(this);
            locked.setText("Device credential confirmation is unavailable.");
            setContentView(locked);
            return;
        }
        startActivityForResult(intent, UNLOCK_REQUEST);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != UNLOCK_REQUEST) return;
        if (resultCode == RESULT_OK) openCompanion();
        else finish();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void openCompanion() {
        if (webView != null) return;
        webView = new WebView(this);
        setContentView(webView);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(false);
        webView.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !"https".equalsIgnoreCase(request.getUrl().getScheme())
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
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
