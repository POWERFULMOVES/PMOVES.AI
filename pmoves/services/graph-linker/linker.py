import os, asyncio, json, re, glob
from nats.aio.client import Client as NATS
from neo4j import GraphDatabase

NEO4J_URL = os.environ.get("NEO4J_URL","bolt://neo4j:7687")
NEO4J_USER = os.environ.get("NEO4J_USER","neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD","neo4j")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE","neo4j")
NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")

def apply_migrations(driver):
    files = sorted(glob.glob("migrations/*.cypher"))
    with driver.session(database=NEO4J_DATABASE) as s:
        for f in files:
            cypher = open(f).read()
            for stmt in [x.strip() for x in cypher.split(';') if x.strip()]:
                s.run(stmt)

def parse_s3(uri:str):
    m = re.match(r'^s3://([^/]+)/(.+)$', uri)
    if not m:
        return None, None
    return m.group(1), m.group(2)

async def handle_gen_image_result(driver, env):
    p = env.get("payload", {})
    uri = p.get("artifact_uri")
    if not uri:
        return
    bucket, key = parse_s3(uri)
    public_url = (p.get("meta") or {}).get("public_url")
    presigned_url = (p.get("meta") or {}).get("presigned_url")
    source = env.get("source","unknown")
    evt_id = env.get("id")
    ts = env.get("ts")
    CYPHER = '''
    MERGE (a:Asset:Image {uri:$uri})
      ON CREATE SET a.created_at = datetime($ts)
    SET a.bucket=$bucket, a.key=$key, a.public_url=$public_url, a.presigned_url=$presigned_url, a.updated_at = datetime($ts)
    MERGE (w:Workflow {name:'comfyui', kind:'image'})
    MERGE (g:Generation {id:$evt_id})
      ON CREATE SET g.ts = datetime($ts), g.source=$source
      ON MATCH SET  g.ts = datetime($ts), g.source=$source
    MERGE (ag:Agent {name:$source})
    MERGE (ag)-[:EMITTED]->(g)
    MERGE (g)-[:PRODUCED]->(a)
    MERGE (g)-[:USED_WORKFLOW]->(w)
    '''
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(CYPHER, uri=uri, bucket=bucket, key=key, public_url=public_url, presigned_url=presigned_url, evt_id=evt_id, ts=ts, source=source)

async def handle_analysis_topics_result(driver, env):
    p = env.get("payload", {})
    media_id = p.get("media_id","unknown")
    topics = p.get("topics", [])
    ts = env.get("ts")
    CYPHER_MEDIA = 'MERGE (m:Media {id:$id}) ON CREATE SET m.created_at=datetime($ts)'
    CYPHER_TOPIC = '''
    MERGE (t:Topic {label:$label})
    ON CREATE SET t.created_at = datetime($ts)
    SET t.last_score = $score, t.updated_at = datetime($ts)
    MERGE (m:Media {id:$mid})
    MERGE (m)-[:HAS_TOPIC {score:$score}]->(t)
    '''
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(CYPHER_MEDIA, id=media_id, ts=ts)
        for t in topics:
            s.run(CYPHER_TOPIC, label=t.get("label"), score=float(t.get("score",0.0)), mid=media_id, ts=ts)

async def handle_kb_upsert_request(driver, env):
    p = env.get("payload", {})
    items = p.get("items", [])
    ns = p.get("namespace","default")
    ts = env.get("ts")
    CYPHER = '''
    MERGE (ns:Namespace {name:$ns})
    WITH ns
    UNWIND $items AS it
      MERGE (k:KBItem {id:it.id})
        ON CREATE SET k.created_at = datetime($ts)
      SET k.text = it.text, k.metadata = it.metadata, k.updated_at = datetime($ts)
      MERGE (ns)-[:CONTAINS]->(k)
    '''
    items2 = [{"id":x.get("id"),"text":x.get("text"),"metadata":x.get("metadata")} for x in items]
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(CYPHER, ns=ns, items=items2, ts=ts)

async def main():
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    apply_migrations(driver)

    async def router(msg):
        try:
            env = json.loads(msg.data.decode())
            topic = env.get("topic","")
            if topic == "gen.image.result.v1":
                await handle_gen_image_result(driver, env)
            elif topic == "analysis.extract_topics.result.v1":
                await handle_analysis_topics_result(driver, env)
            elif topic == "kb.upsert.request.v1":
                await handle_kb_upsert_request(driver, env)
        except Exception as e:
            print("router error:", e)

    await nc.subscribe("gen.image.result.v1", cb=router)
    await nc.subscribe("analysis.extract_topics.result.v1", cb=router)
    await nc.subscribe("kb.upsert.request.v1", cb=router)
    print("graph-linker ready")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
