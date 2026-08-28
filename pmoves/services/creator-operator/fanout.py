"""Fan a validated operator-result out to all sinks. Sinks are injected so the
orchestration is unit-testable with fakes; production sinks wrap NATS/Notebook/
Discord/n8n. Validate-before-emit: an invalid result reaches no sink."""
from schemas import validate_result
from attribution import build_cgp_point, summarize_transcript
from n8n_export import to_n8n_workflow


async def emit_result(result: dict, workorder: dict, sinks, *, model_id: str, license_name: str) -> dict:
    validate_result(result)  # raises before any sink sees it
    cgp = build_cgp_point(result, workorder, model_id=model_id, license_name=license_name)
    result = dict(result, cgp_point=cgp)
    summary = summarize_transcript(result["transcript"])
    n8n_wf = to_n8n_workflow(result, workflow_id=workorder["workflow_id"])

    await sinks.publish_nats("creator.operator.result.v1", result)
    await sinks.write_notebook(result["transcript"])
    await sinks.notify_discord(summary, result.get("artifact"))
    await sinks.save_n8n(n8n_wf)
    return result
