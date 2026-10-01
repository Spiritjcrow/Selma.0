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
    private TextToSpeech tts;
    private boolean ttsReady;
    private String ttsVoiceName;
    private SpeechRecognizer recognizer;

    public SelmaNativeBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        this.tts = new TextToSpeech(activity.getApplicationContext(), this);
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
                if (best == null || voice.getQuality() > best.getQuality()) {
                    best = voice;
                }
            }
        }
        if (best != null && tts.setVoice(best) != TextToSpeech.ERROR) {
            ttsReady = true;
            ttsVoiceName = best.getName();
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String utteranceId) {
                    emit("tts-state", "speaking");
                }
                @Override public void onDone(String utteranceId) {
                    emit("tts-state", "idle");
                }
                @Override public void onError(String utteranceId) {
                    emit("tts-state", "error");
                }
            });
        } else {
            ttsReady = false;
            ttsVoiceName = null;
        }
        emitStatus();
    }

    @JavascriptInterface public void speak(String text) {
        final String value = text == null ? "" : text.trim();
        if (value.isEmpty()) return;
        activity.runOnUiThread(() -> {
            if (!ttsReady || tts == null) {
                emit("tts-error", "No installed offline Android TTS voice is available.");
                return;
            }
            tts.speak(value, TextToSpeech.QUEUE_FLUSH, null, "selma-adult-mode");
        });
    }

    @JavascriptInterface public void stopSpeaking() {
        activity.runOnUiThread(() -> {
            if (tts != null) tts.stop();
        });
    }

    @JavascriptInterface public String voiceStatus() {
        boolean onDeviceAsr = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
            && SpeechRecognizer.isOnDeviceRecognitionAvailable(activity);
        return "{"
            + "\"offlineTts\":" + ttsReady + ","
            + "\"ttsVoice\":" + JSONObject.quote(ttsVoiceName == null ? "" : ttsVoiceName) + ","
            + "\"onDeviceAsr\":" + onDeviceAsr + ","
            + "\"microphoneGranted\":" + (
                activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
            )
            + "}";
    }

    @JavascriptInterface public void startListening() {
        activity.runOnUiThread(() -> {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || !SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) {
                emit("asr-error", "On-device speech recognition is unavailable on this device.");
                return;
            }
            if (activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
                activity.requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    RECORD_AUDIO_REQUEST
                );
                return;
            }
            startRecognizer();
        });
    }

    @JavascriptInterface public void stopListening() {
        activity.runOnUiThread(() -> {
            if (recognizer != null) recognizer.stopListening();
        });
    }

    public void onRecordAudioPermissionResult(boolean granted) {
        if (granted) startListening();
        else emit("asr-error", "Microphone permission was not granted.");
        emitStatus();
    }

    private void startRecognizer() {
        destroyRecognizer();
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S
            || !SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) {
            emit("asr-error", "On-device speech recognition is unavailable.");
            return;
        }
        recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(activity);
        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) {
                emit("asr-state", "listening");
            }
            @Override public void onBeginningOfSpeech() {
                emit("asr-state", "speech");
            }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() {
                emit("asr-state", "processing");
            }
            @Override public void onError(int error) {
                emit("asr-error", "Android on-device recognizer error " + error);
                destroyRecognizer();
            }
            @Override public void onResults(Bundle results) {
                emitBestResult("final", results);
                destroyRecognizer();
            }
            @Override public void onPartialResults(Bundle partialResults) {
                emitBestResult("partial", partialResults);
            }
            @Override public void onEvent(int eventType, Bundle params) { }
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(
            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
        );
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag());
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        recognizer.startListening(intent);
    }

    private void emitBestResult(String kind, Bundle bundle) {
        if (bundle == null) return;
        ArrayList<String> values = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (values != null && !values.isEmpty()) emit(kind, values.get(0));
    }

    private void emitStatus() {
        emit("voice-status", voiceStatus());
    }

    private void emit(String kind, String value) {
        final String script = "window.selmaNativeSpeech&&window.selmaNativeSpeech("
            + JSONObject.quote(kind) + "," + JSONObject.quote(value == null ? "" : value) + ")";
        webView.post(() -> webView.evaluateJavascript(script, null));
    }

    private void destroyRecognizer() {
        if (recognizer != null) {
            recognizer.cancel();
            recognizer.destroy();
            recognizer = null;
        }
    }

    public void destroy() {
        destroyRecognizer();
        if (tts != null) {
            tts.stop();
            tts.shutdown();
            tts = null;
        }
        ttsReady = false;
    }
}
