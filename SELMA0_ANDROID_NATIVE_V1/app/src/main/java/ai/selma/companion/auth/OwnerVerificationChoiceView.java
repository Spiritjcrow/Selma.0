package ai.selma.companion.auth;

import android.content.Context;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;

/**
 * Review-only owner verification selector. Not attached to a protected Activity.
 * The host must supply an independently trusted, owner-bound evidence provider.
 */
public final class OwnerVerificationChoiceView extends LinearLayout {
    public interface EvidenceProvider {
        boolean supports(OwnerVerificationGate.Method method);
        void request(OwnerVerificationGate.Attempt challenge, Callback callback);
    }
    public interface Callback {
        void onResult(OwnerVerificationGate.Method method, String nonce, byte[] proof);
    }
    private final OwnerVerificationGate gate;
    private final EvidenceProvider provider;
    private final RadioGroup choices;
    private final TextView status;
    private final Button tryAgain;

    public OwnerVerificationChoiceView(Context context, OwnerVerificationGate gate,
                                       EvidenceProvider provider) {
        super(context);
        this.gate = gate;
        this.provider = provider;
        setOrientation(VERTICAL);
        setPadding(20, 20, 20, 20);
        setBackgroundColor(Color.rgb(17, 19, 27));

        TextView heading = new TextView(context);
        heading.setText("Choose a verification option");
        heading.setTextSize(22);
        heading.setTextColor(Color.WHITE);
        heading.setGravity(Gravity.CENTER);
        addView(heading);

        choices = new RadioGroup(context);
        choices.setOrientation(VERTICAL);
        addChoice(context, "Fingerprint", OwnerVerificationGate.Method.FINGERPRINT, 101);
        addChoice(context, "Face recognition", OwnerVerificationGate.Method.FACE, 102);
        addChoice(context, "Voice spectrum verification", OwnerVerificationGate.Method.VOICE, 103);
        addView(choices);

        Button tryThis = new Button(context);
        tryThis.setText("Try this");
        tryThis.setOnClickListener(v -> startSelected());
        addView(tryThis);

        tryAgain = new Button(context);
        tryAgain.setText("Try again new option to verify");
        tryAgain.setOnClickListener(v -> {
            gate.tryAgainNewOption();
            choices.clearCheck();
            status.setText("Choose another available method. The feature remains locked.");
        });
        addView(tryAgain);

        status = new TextView(context);
        status.setTextColor(Color.WHITE);
        status.setText("Locked. Select one available method.");
        addView(status);
    }

    private void addChoice(Context context, String label, OwnerVerificationGate.Method method,
                           int id) {
        RadioButton button = new RadioButton(context);
        button.setId(id);
        boolean available = provider != null && provider.supports(method);
        button.setEnabled(available);
        button.setText(label + (available ? "" : " — not configured"));
        button.setTextColor(Color.WHITE);
        choices.addView(button);
    }

    private void startSelected() {
        OwnerVerificationGate.Method method;
        switch (choices.getCheckedRadioButtonId()) {
            case 101: method = OwnerVerificationGate.Method.FINGERPRINT; break;
            case 102: method = OwnerVerificationGate.Method.FACE; break;
            case 103: method = OwnerVerificationGate.Method.VOICE; break;
            default:
                status.setText("Choose an available verification option first.");
                return;
        }
        if (provider == null || !provider.supports(method)) {
            status.setText("Selected verification provider is not configured. Still locked.");
            return;
        }
        gate.select(method);
        OwnerVerificationGate.Attempt attempt = gate.tryThis();
        status.setText("Waiting for " + method.name().toLowerCase() + " verification…");
        try {
            provider.request(attempt, (actualMethod, nonce, proof) -> post(() -> {
                boolean verified = gate.submitProof(actualMethod, nonce, proof);
                status.setText(verified
                    ? "Verification evidence accepted by trusted owner validator."
                    : "Verification unsuccessful. Feature remains locked. Try a new option.");
            }));
        } catch (RuntimeException error) {
            gate.tryAgainNewOption();
            status.setText("Verification unavailable. Feature remains locked.");
        }
    }

    @Override protected void onDetachedFromWindow() {
        gate.lock();
        super.onDetachedFromWindow();
    }
}
