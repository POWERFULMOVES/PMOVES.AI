import { NextResponse } from 'next/server';

import {
  ArchonPromptInput,
  DuplicatePromptNameError,
  PolicyViolationError,
  createArchonPrompt,
} from '../../../lib/archonPrompts';

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

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as ArchonPromptInput;
    const created = await createArchonPrompt(payload);
    return NextResponse.json({ data: created }, { status: 201 });
  } catch (error) {
    return mapErrorToResponse(error);
  }
}
