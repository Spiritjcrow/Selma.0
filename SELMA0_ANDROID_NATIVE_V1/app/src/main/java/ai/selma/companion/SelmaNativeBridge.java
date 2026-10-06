package ai.selma.companion;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import java.util.ArrayList;
import java.util.Locale;
import org.json.JSONObject;

public final class SelmaNativeBridge implements TextToSpeech.OnInitListener {
    public static final int RECORD_AUDIO_REQUEST = 7101;
    private final Activity activity;
    private final WebView webView;
    private final NativeAuthority authority = new NativeAuthority();
    private TextToSpeech tts;
    private boolean ttsReady;
    private String ttsVoiceName;
    private SpeechRecognizer recognizer;
    private long recognitionGeneration;
    private long pendingPermissionDocument = -1L;
    private long pendingNavigationGeneration = -1L;
    private String pendingNavigationUrl;

    public SelmaNativeBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        tts = new TextToSpeech(activity.getApplicationContext(), this);
    }

    void onNavigationStarted(String url) {
        pendingNavigationGeneration = authority.navigationStarted();
        pendingNavigationUrl = url;
        invalidateRecognition();
    }

    void onNavigationCommitted(String url) {
        if (pendingNavigationUrl == null || !pendingNavigationUrl.equals(url)) return;
        authority.navigationCommitted(pendingNavigationGeneration, url);
        pendingNavigationGeneration = -1L;
        pendingNavigationUrl = null;
        if (authority.activeGeneration() >= 0) emitStatus();
    }

    void revokeAuthority() {
        pendingNavigationGeneration = -1L;
        pendingNavigationUrl = null;
        authority.revoke();
        invalidateRecognition();
    }

    @Override public void onInit(int status) {
        if (status != TextToSpeech.SUCCESS || tts == null) {
            ttsReady = false;
            emitStatus();
            return;
        }
        Voice best = null;
        if (tts.getVoices() != null) {
            for (Voice voice : tts.getVoices()) {
                if (voice == null || voice.isNetworkConnectionRequired()) continue;
                Locale locale = voice.getLocale();
                if (locale == null || !Locale.ENGLISH.getLanguage().equals(locale.getLanguage())) continue;
                if (best == null || voice.getQuality() > best.getQuality()) best = voice;
            }
        }
        if (best != null && tts.setVoice(best) != TextToSpeech.ERROR) {
            ttsReady = true;
            ttsVoiceName = best.getName();
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String id) { emitForUtterance(id, "speaking"); }
                @Override public void onDone(String id) { emitForUtterance(id, "idle"); }
                @Override public void onError(String id) { emitForUtterance(id, "error"); }
            });
        } else {
            ttsReady = false;
            ttsVoiceName = null;
        }
        emitStatus();
    }

    @JavascriptInterface public void speak(String text) {
        String value = text == null ? "" : text.trim();
        long document = authority.activeGeneration();
        if (value.isEmpty() || document < 0) return;
        activity.runOnUiThread(() -> {
            if (!authority.owns(document)) return;
            if (!ttsReady || tts == null) {
                emit(document, "tts-error", "No installed offline Android TTS voice is available.");
                return;
            }
            tts.speak(value, TextToSpeech.QUEUE_FLUSH, null, "selma-" + document);
        });
    }

    @JavascriptInterface public void stopSpeaking() {
        long document = authority.activeGeneration();
        if (document < 0) return;
        activity.runOnUiThread(() -> { if (authority.owns(document) && tts != null) tts.stop(); });
    }

    @JavascriptInterface public String voiceStatus() {
        if (authority.activeGeneration() < 0) return "{}";
        boolean onDeviceAsr = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
            && SpeechRecognizer.isOnDeviceRecognitionAvailable(activity);
        return "{" + "\"offlineTts\":" + ttsReady + ","
            + "\"ttsVoice\":" + JSONObject.quote(ttsVoiceName == null ? "" : ttsVoiceName) + ","
            + "\"onDeviceAsr\":" + onDeviceAsr + ","
            + "\"microphoneGranted\":"
            + (activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
            + "}";
    }

    @JavascriptInterface public void startListening() {
        long document = authority.activeGeneration();
        if (document < 0) return;
        activity.runOnUiThread(() -> {
            if (!authority.owns(document)) return;
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || !SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) {
                emit(document, "asr-error", "On-device speech recognition is unavailable on this device.");
                return;
            }
            if (activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                pendingPermissionDocument = document;
                activity.requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, RECORD_AUDIO_REQUEST);
                return;
            }
            startRecognizer(document);
        });
    }

    @JavascriptInterface public void stopListening() {
        long document = authority.activeGeneration();
        if (document < 0) return;
        activity.runOnUiThread(() -> { if (authority.owns(document)) invalidateRecognition(); });
    }

    public void onRecordAudioPermissionResult(boolean granted) {
        long document = pendingPermissionDocument;
        pendingPermissionDocument = -1L;
        if (!authority.owns(document)) return;
        if (granted) startRecognizer(document);
        else emit(document, "asr-error", "Microphone permission was not granted.");
        emitStatus();
    }

    private void startRecognizer(long document) {
        if (!authority.owns(document)) return;
        invalidateRecognition();
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S
            || !SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) {
            emit(document, "asr-error", "On-device speech recognition is unavailable.");
            return;
        }
        long session = ++recognitionGeneration;
        SpeechRecognizer created = SpeechRecognizer.createOnDeviceSpeechRecognizer(activity);
        recognizer = created;
        created.setRecognitionListener(new RecognitionListener() {
            private boolean current() {
                return recognizer == created && recognitionGeneration == session && authority.owns(document);
            }
            @Override public void onReadyForSpeech(Bundle p) { if (current()) emit(document, "asr-state", "listening"); }
            @Override public void onBeginningOfSpeech() { if (current()) emit(document, "asr-state", "speech"); }
            @Override public void onRmsChanged(float value) { }
            @Override public void onBufferReceived(byte[] value) { }
            @Override public void onEndOfSpeech() { if (current()) emit(document, "asr-state", "processing"); }
            @Override public void onError(int error) {
                if (!current()) return;
                emit(document, "asr-error", "Android on-device recognizer error " + error);
                finishRecognizer(created, session);
            }
            @Override public void onResults(Bundle results) {
                if (!current()) return;
                emitBestResult(document, "final", results);
                finishRecognizer(created, session);
            }
            @Override public void onPartialResults(Bundle results) {
                if (current()) emitBestResult(document, "partial", results);
            }
            @Override public void onEvent(int type, Bundle params) { }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag());
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        created.startListening(intent);
    }

    private void emitBestResult(long document, String kind, Bundle bundle) {
        if (!authority.owns(document) || bundle == null) return;
        ArrayList<String> values = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (values != null && !values.isEmpty()) emit(document, kind, values.get(0));
    }

    private void emitStatus() {
        long document = authority.activeGeneration();
        if (document >= 0) emit(document, "voice-status", voiceStatus());
    }

    private void emitForUtterance(String id, String state) {
        if (id == null || !id.startsWith("selma-")) return;
        try { emit(Long.parseLong(id.substring(6)), "tts-state", state); }
        catch (NumberFormatException ignored) { }
    }

    private void emit(long document, String kind, String value) {
        if (!authority.owns(document)) return;
        String script = "window.selmaNativeSpeech&&window.selmaNativeSpeech("
            + JSONObject.quote(kind) + "," + JSONObject.quote(value == null ? "" : value) + ")";
        webView.post(() -> { if (authority.owns(document)) webView.evaluateJavascript(script, null); });
    }

    private void finishRecognizer(SpeechRecognizer target, long session) {
        if (recognizer != target || recognitionGeneration != session) return;
        recognizer = null;
        target.destroy();
    }

    private void invalidateRecognition() {
        pendingPermissionDocument = -1L;
        recognitionGeneration++;
        SpeechRecognizer old = recognizer;
        recognizer = null;
        if (old != null) {
            old.cancel();
            old.destroy();
        }
    }

    public void destroy() {
        revokeAuthority();
        if (tts != null) {
            tts.stop();
            tts.shutdown();
            tts = null;
        }
        ttsReady = false;
    }
}
