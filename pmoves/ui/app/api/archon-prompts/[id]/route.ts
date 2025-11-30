import { NextResponse } from 'next/server';

import {
  ArchonPromptInput,
  DuplicatePromptNameError,
  PolicyViolationError,
  deleteArchonPrompt,
  updateArchonPrompt,
} from '../../../../lib/archonPrompts';

function mapErrorToResponse(error: unknown) {
  if (error instanceof DuplicatePromptNameError) {
    return NextResponse.json(
      { error: { type: 'DuplicatePromptNameError', message: error.message } },
      { status: 409 }
    );
  }

  if (error instanceof PolicyViolationError) {
    return NextResponse.json(
      { error: { type: 'PolicyViolationError', message: error.message } },
      { status: 403 }
    );
  }

  const message = error instanceof Error ? error.message : 'Unexpected Supabase error.';
  return NextResponse.json({ error: { message } }, { status: 500 });
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: { message: 'Prompt id is required.' } }, { status: 400 });
    }

    const payload = (await request.json()) as ArchonPromptInput;
    const updated = await updateArchonPrompt(id, payload);
    return NextResponse.json({ data: updated });
  } catch (error) {
    return mapErrorToResponse(error);
  }
}

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: { message: 'Prompt id is required.' } }, { status: 400 });
    }

    await deleteArchonPrompt(id);
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    return mapErrorToResponse(error);
  }
}
