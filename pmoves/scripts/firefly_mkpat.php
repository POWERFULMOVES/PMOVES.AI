<?php
// firefly_mkpat.php — Firefly III passport PAT helper for the auto-mint script.
// Runs INSIDE the Firefly container (base64-injected to /tmp by firefly_automint.sh).
//
// PAT_MODE=mint   (default) mint a Personal Access Token for PAT_EMAIL named PAT_NAME.
//                 Writes the plaintext JWT to /tmp/pmoves_pat (createToken returns it
//                 exactly once) and the token id to /tmp/pmoves_pat_id.
// PAT_MODE=revoke revoke tokens for PAT_EMAIL named PAT_NAME:
//                   PAT_ONLY_ID=<id>  revoke just that token (failure-path cleanup)
//                   PAT_KEEP_ID=<id>  revoke every OTHER live token of that name
//                                     (supersede the previous baseline PAT)
// The user must already exist (auto-provisioned via the Remote-User web guard) and a
// passport personal-access client must exist (`php artisan passport:client --personal`).
require "/var/www/html/vendor/autoload.php";
$app = require "/var/www/html/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

$email = getenv("PAT_EMAIL");
$name = getenv("PAT_NAME") ?: "wealth-mcp-automint";
$mode = getenv("PAT_MODE") ?: "mint";
if (!$email) { fwrite(STDERR, "PAT_EMAIL not set\n"); exit(2); }

$user = FireflyIII\User::where("email", $email)->first();
if (!$user) { fwrite(STDERR, "no Firefly user for {$email} (provision via Remote-User first)\n"); exit(1); }

if ($mode === "revoke") {
    $q = $user->tokens()->where("name", $name)->where("revoked", false);
    if ($only = getenv("PAT_ONLY_ID")) { $q->where("id", $only); }
    elseif ($keep = getenv("PAT_KEEP_ID")) { $q->where("id", "!=", $keep); }
    else { fwrite(STDERR, "revoke needs PAT_ONLY_ID or PAT_KEEP_ID\n"); exit(2); }
    $n = $q->update(["revoked" => true]);
    echo "revoked {$n} token(s) named {$name} for {$email}\n";
    exit(0);
}

$token = $user->createToken($name);
file_put_contents("/tmp/pmoves_pat", $token->accessToken);
file_put_contents("/tmp/pmoves_pat_id", $token->token->id);
echo "minted PAT for {$email} (len=" . strlen($token->accessToken) . ")\n";
