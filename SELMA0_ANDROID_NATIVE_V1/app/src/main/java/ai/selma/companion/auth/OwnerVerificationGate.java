package ai.selma.companion.auth;

import java.security.SecureRandom;
import java.util.Objects;

/**
 * App-local state machine only. Not an identity provider or an authorization grant.
 * A trusted proof verifier must bind evidence to owner, session, nonce and selected modality.
 */
public final class OwnerVerificationGate {
    public enum Method { FINGERPRINT, FACE, VOICE }
    public enum State { LOCKED, SELECTED, VERIFYING, VERIFIED }

    public interface Clock { long nowMs(); }
    public interface ProofVerifier {
        boolean verifyOwnerProof(Method method, String nonce, byte[] proof);
    }
    public static final class Attempt {
        public final Method method;
        public final String nonce;
        public final long expiresAtMs;
        private Attempt(Method method, String nonce, long expiresAtMs) {
            this.method = method;
            this.nonce = nonce;
            this.expiresAtMs = expiresAtMs;
        }
    }
    private static final long ATTEMPT_TTL_MS = 45_000L;
    private static final char[] HEX = "0123456789abcdef".toCharArray();
    private final SecureRandom random = new SecureRandom();
    private final Clock clock;
    private final ProofVerifier verifier;
    private Method selected;
    private Attempt pending;
    private State state = State.LOCKED;

    public OwnerVerificationGate(Clock clock, ProofVerifier verifier) {
        this.clock = Objects.requireNonNull(clock);
        this.verifier = Objects.requireNonNull(verifier);
    }

    public synchronized void select(Method method) {
        selected = Objects.requireNonNull(method);
        pending = null;
        state = State.SELECTED;
    }

    /** Triggered by the "Try this" selection. One chosen method is sufficient. */
    public synchronized Attempt tryThis() {
        if (state != State.SELECTED || selected == null) {
            throw new IllegalStateException("Choose a verification method first");
        }
        byte[] nonceBytes = new byte[24];
        random.nextBytes(nonceBytes);
        char[] encoded = new char[nonceBytes.length * 2];
        for (int i = 0; i < nonceBytes.length; i++) {
            encoded[i * 2] = HEX[(nonceBytes[i] >>> 4) & 15];
            encoded[i * 2 + 1] = HEX[nonceBytes[i] & 15];
        }
        pending = new Attempt(selected, new String(encoded), clock.nowMs() + ATTEMPT_TTL_MS);
        state = State.VERIFYING;
        return pending;
    }

    /** A bare UI success callback or device-sensor response is not owner proof. */
    public synchronized boolean submitProof(Method method, String nonce, byte[] proof) {
        if (state != State.VERIFYING || pending == null || method != pending.method
                || nonce == null || !nonce.equals(pending.nonce)
                || proof == null || proof.length == 0 || clock.nowMs() > pending.expiresAtMs) {
            failClosed();
            return false;
        }
        boolean approved;
        try {
            approved = verifier.verifyOwnerProof(method, nonce, proof.clone());
        } catch (RuntimeException error) {
            approved = false;
        }
        pending = null; // single use, including failed verification
        state = approved ? State.VERIFIED : State.SELECTED;
        return approved;
    }

    /** "Try again new option to verify" returns to method selection. */
    public synchronized void tryAgainNewOption() {
        pending = null;
        selected = null;
        state = State.LOCKED;
    }

    public synchronized void lock() { tryAgainNewOption(); }
    public synchronized boolean isVerified() { return state == State.VERIFIED; }
    public synchronized State getState() { return state; }
    public synchronized Method getSelected() { return selected; }

    private void failClosed() {
        pending = null;
        state = selected == null ? State.LOCKED : State.SELECTED;
    }
}
