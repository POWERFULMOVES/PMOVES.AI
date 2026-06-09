import asyncio
from fanout import emit_result
from fixtures import VALID_RESULT, VALID_WORKORDER


class FakeSinks:
    def __init__(self):
        self.nats = []
        self.notebook = []
        self.discord = []
        self.n8n = []

    async def publish_nats(self, subject, payload):
        self.nats.append((subject, payload))

    async def write_notebook(self, transcript):
        self.notebook.append(transcript)

    async def notify_discord(self, summary, artifact):
        self.discord.append((summary, artifact))

    async def save_n8n(self, workflow):
        self.n8n.append(workflow)


def test_emit_result_fans_out_all_sinks():
    sinks = FakeSinks()
    asyncio.run(emit_result(VALID_RESULT, VALID_WORKORDER, sinks,
                            model_id="ideogram-4", license="non-commercial"))
    assert sinks.nats and sinks.nats[0][0] == "creator.operator.result.v1"
    assert sinks.notebook and sinks.notebook[0] == VALID_RESULT["transcript"]
    assert sinks.discord and "seed" in sinks.discord[0][0]
    assert sinks.n8n and sinks.n8n[0]["nodes"][0]["parameters"]["workorder_id"] == "wo_test1"


def test_emit_result_validates_before_fanout():
    sinks = FakeSinks()
    bad = dict(VALID_RESULT, status="maybe")
    try:
        asyncio.run(emit_result(bad, VALID_WORKORDER, sinks, model_id="x", license="y"))
        assert False, "should have raised on invalid result"
    except Exception:
        assert sinks.nats == []  # nothing emitted on invalid result
