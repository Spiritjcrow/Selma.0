package ai.selma.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

public final class MainActivity extends Activity {
    private static final String SELMA_LOCAL_URL = "http://127.0.0.1:8765/adult-mode";
    private WebView webView;

    private static boolean isAllowedLocalUri(Uri uri) {
        if (uri == null) return false;
        String scheme = uri.getScheme();
        String host = uri.getHost();
        if ("about".equalsIgnoreCase(scheme)) return true;
        if (!"http".equalsIgnoreCase(scheme) || host == null) return false;
        return "127.0.0.1".equals(host)
            || "localhost".equalsIgnoreCase(host)
            || "::1".equals(host);
    }

    private static WebResourceResponse blockedResponse() {
        byte[] body = "Selma Native blocks non-local network resources.".getBytes(StandardCharsets.UTF_8);
        return new WebResourceResponse(
            "text/plain",
            "UTF-8",
            new ByteArrayInputStream(body)
        );
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !isAllowedLocalUri(request.getUrl());
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (!isAllowedLocalUri(request.getUrl())) {
                    return blockedResponse();
                }
                return super.shouldInterceptRequest(view, request);
            }

            @Override public void onReceivedError(
                WebView view,
                WebResourceRequest request,
                android.webkit.WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    String html = "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
                        + "<style>body{font:16px system-ui;background:#090b10;color:#eef;padding:24px}"
                        + "button{padding:12px 18px}</style>"
                        + "<h1>Selma Adult Mode</h1>"
                        + "<p>The local Selma runtime is not answering yet.</p>"
                        + "<p>Start the Termux Selma runtime, then retry. No cloud fallback is used here.</p>"
                        + "<button onclick=\"location.href='" + SELMA_LOCAL_URL + "'\">Retry local Selma</button>";
                    view.loadDataWithBaseURL("about:blank", html, "text/html", "UTF-8", null);
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(request::deny);
            }
        });

        webView.loadUrl(SELMA_LOCAL_URL);
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
