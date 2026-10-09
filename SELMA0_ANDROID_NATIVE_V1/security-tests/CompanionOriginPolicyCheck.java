import ai.selma.companion.CompanionOriginPolicy;

/** Pure-Java, no-network regression cases. Run with javac and java. */
public final class CompanionOriginPolicyCheck {
    private static int count = 0;

    private static void check(String url, boolean expected) {
        count++;
        if (CompanionOriginPolicy.isTrusted(url) != expected) {
            throw new AssertionError("Unexpected result for origin-policy case " + count);
        }
    }

    public static void main(String[] args) {
        String good = "https://selma-official-companion.spiritjcrow1990.chatgpt.site";
        check(good, true);
        check(good + "/settings?q=ok", true);
        check(good.replace("https:", "HTTP:"), false);
        check("https://evilchatgpt.site/", false);
        check("https://selma-official-companion.spiritjcrow1990.chatgpt.site.evil.test", false);
        check("https://selma-official-companion.spiritjcrow1990.chatgpt.site@evil.test/", false);
        check(good + ":8443/", false);
        check(good + ":443/", true);
        check("https://sub." + good.substring("https://".length()), false);
        check("file:///data/local/tmp/index.html", false);
        check("javascript:alert(1)", false);
        check(null, false);
        check("not a url", false);
        System.out.println("PASS " + count + " Java origin-policy cases");
    }
}
