import secrets, string, sys
from pathlib import Path

# Generates the synthetic recall fixture set (FAKE credentials only).
# Committed as a generator instead of fixtures because GitHub push
# protection rejects pushes containing real-format credential strings,
# even synthetic ones. Output: pmoves/chat-corpus/recall-cases/

OUT = Path(__file__).parent / "recall-cases"
OUT.mkdir(exist_ok=True)

def rnd(chars, n):
    return "".join(secrets.choice(chars) for _ in range(n))

AL = string.ascii_letters + string.digits + "-_"
HX = "0123456789abcdef"
UP = string.ascii_uppercase + "0123456789"
B64 = string.ascii_letters + string.digits + "+/"

jwt_h = rnd(AL, 36); jwt_p = rnd(AL, 43); jwt_s = rnd(AL, 43)
fine = "github_pat_" + rnd(string.ascii_letters + string.digits, 22) + "_" + rnd(string.ascii_letters + string.digits, 59)
files = {
 "01_aws.txt": "aws_id = AKIA" + rnd(UP, 16) + "\naws_secret = " + rnd(string.ascii_letters + string.digits + "/+", 40) + "\n",
 "02_github_classic.txt": "token: ghp_" + rnd(string.ascii_letters + string.digits, 36) + "\n",
 "03_github_finegrained.txt": "token: " + fine + "\n",
 "04_slack.txt": "slack = xoxb-" + rnd(string.digits, 12) + "-" + rnd(string.digits, 13) + "-" + rnd(string.ascii_letters + string.digits, 24) + "\n",
 "05_stripe.txt": "stripe key sk_test_" + rnd(string.ascii_letters + string.digits, 24) + "\n",
 "06_google.txt": "google api key: AIza" + rnd(AL, 35) + "\n",
 "07_openai_proj.txt": "openai sk-proj-" + rnd(AL, 56) + "T3BlbkFJ" + rnd(string.ascii_letters + string.digits, 43) + "\n",
 "08_sendgrid.txt": "sendgrid SG." + rnd(string.ascii_letters + string.digits, 22) + "." + rnd(string.ascii_letters + string.digits, 43) + "\n",
 "09_twilio.txt": "twilio SK" + rnd(HX, 32) + "\n",
 "10_jwt.txt": "Authorization: Bearer eyJ" + jwt_h + ".eyJ" + jwt_p + "." + jwt_s + "\n",
 "11_jwt_json_escaped.txt": '{"accessToken": "eyJ' + jwt_h + '.eyJ' + rnd(AL, 20) + '"}\n',
 "12_postgres_url.txt": "postgresql://admin:" + rnd(AL, 20) + "@db.example.internal:5432/prod\n",
 "13_env_assignments.txt": "DB_PASSWORD=" + rnd(string.ascii_letters + string.digits, 16) + "\nexport API_SECRET_KEY = \"" + rnd(string.ascii_lowercase + string.digits, 18) + "\"\nREFRESH_TOKEN=" + rnd(string.ascii_lowercase + string.digits, 18) + "\n",
 "14_lan_ips.txt": "gateway 10." + rnd(string.digits, 1) + "." + rnd(string.digits, 2) + "." + rnd(string.digits, 2) + " up\nprinter 192.168." + rnd(string.digits, 1) + "." + rnd(string.digits, 2) + "\nnas 172.16." + rnd(string.digits, 1) + "." + rnd(string.digits, 2) + "\n",
 "19_negative_ips.txt": "public 8.8.8.8\nnear-miss 172.15.255.1\nout-of-range 172.32.0.1\n",
 "15_private_key.txt": "-----BEGIN RSA PRIVATE KEY-----\n" + rnd(B64, 64) + "\n" + rnd(B64, 64) + "\n-----END RSA PRIVATE KEY-----\n",
 "16_generic_named.txt": "api_key = \"" + rnd(HX, 32) + "\"\n",
 "17_generic_bare.txt": rnd(HX, 32) + "\n",
 "18_base64_blob.txt": rnd(B64, 72) + "\n",
}
for name, content in files.items():
    (OUT / name).write_text(content, encoding="ascii")
print("wrote", len(files), "fixtures to", OUT)
print("scan: gitleaks detect --source", OUT, "--no-git --config pmoves/chat-corpus/gitleaks.toml --report-format json --report-path r.json --no-banner")
