import ai.selma.companion.auth.OwnerVerificationGate;
import ai.selma.companion.auth.OwnerVerificationGate.Method;
import ai.selma.companion.auth.OwnerVerificationGate.Attempt;

public final class OwnerVerificationGateTest {
    private static final class Clock implements OwnerVerificationGate.Clock {
        long now = 100000L;
        public long nowMs() { return now; }
    }
    private static final byte[] VALID = {4, 2};
    private static void check(boolean value, String name) {
        if (!value) throw new AssertionError(name);
        System.out.println("PASS " + name);
    }
    public static void main(String[] args) {
        Clock time = new Clock();
        OwnerVerificationGate gate = new OwnerVerificationGate(time,
                (method, nonce, proof) -> proof.length == 2 && proof[0] == 4 && proof[1] == 2);
        check(!gate.isVerified(), "initially locked");
        try { gate.tryThis(); throw new AssertionError("no selection"); }
        catch (IllegalStateException expected) { check(true, "cannot try without selection"); }
        for (Method method : Method.values()) {
            gate.select(method);
            Attempt attempt = gate.tryThis();
            check(attempt.method == method && attempt.nonce.length() == 48, "fresh nonce " + method);
            check(!gate.submitProof(method, attempt.nonce + "x", VALID), "nonce mismatch rejects " + method);
            Attempt retry = gate.tryThis();
            check(!retry.nonce.equals(attempt.nonce), "new nonce " + method);
            check(gate.submitProof(method, retry.nonce, VALID), "one valid selected method sufficient " + method);
            check(!gate.submitProof(method, retry.nonce, VALID), "replay rejects " + method);
        }
        gate.select(Method.VOICE);
        Attempt expired = gate.tryThis();
        time.now += 45001;
        check(!gate.submitProof(Method.VOICE, expired.nonce, VALID), "expiration rejects");
        gate.select(Method.FACE);
        Attempt wrong = gate.tryThis();
        check(!gate.submitProof(Method.FINGERPRINT, wrong.nonce, VALID), "method mismatch rejects");
        gate.select(Method.FACE);
        Attempt invalid = gate.tryThis();
        check(!gate.submitProof(Method.FACE, invalid.nonce, new byte[]{0}), "invalid owner proof rejects");
        gate.select(Method.FINGERPRINT);
        gate.tryThis();
        gate.tryAgainNewOption();
        check(gate.getState() == OwnerVerificationGate.State.LOCKED && gate.getSelected() == null,
                "try again new option resets method");
        gate.select(Method.VOICE);
        Attempt finalAttempt = gate.tryThis();
        check(gate.submitProof(Method.VOICE, finalAttempt.nonce, VALID), "valid independent option");
        gate.lock();
        check(!gate.isVerified(), "background lock clears grant");
    }
}
