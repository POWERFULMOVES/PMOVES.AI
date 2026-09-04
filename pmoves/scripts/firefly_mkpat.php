<?php
// firefly_mkpat.php — mint a Firefly III API Personal Access Token (passport) for a user,
// writing the plaintext JWT to /tmp/pmoves_pat (createToken returns it exactly once).
// Runs INSIDE the Firefly container via the auto-mint script; no tinker needed.
// The user must already exist (auto-provisioned via the Remote-User web guard) and a
// passport personal-access client must exist (`php artisan passport:client --personal`).
require "/var/www/html/vendor/autoload.php";
$app = require "/var/www/html/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

$email = getenv("PAT_EMAIL");
$name = getenv("PAT_NAME") ?: "wealth-mcp-automint";
if (!$email) { fwrite(STDERR, "PAT_EMAIL not set\n"); exit(2); }

$user = FireflyIII\User::where("email", $email)->first();
if (!$user) { fwrite(STDERR, "no Firefly user for {$email} (provision via Remote-User first)\n"); exit(1); }

$token = $user->createToken($name);
file_put_contents("/tmp/pmoves_pat", $token->accessToken);
echo "minted PAT for {$email} (len=" . strlen($token->accessToken) . ")\n";
