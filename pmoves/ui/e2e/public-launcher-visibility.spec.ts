import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type TestInfo } from '@playwright/test';

/**
 * @launcher-visibility
 *
 * The unauthenticated home page (app/page.tsx) server-renders a room launcher
 * from lib/rooms.ts loadPublicRooms(). A room must reach it ONLY when its
 * manifest says access.visibility === 'public' (and is not owner_only /
 * exclude_from_public_catalog). From #3165 until #3218 the predicate failed
 * OPEN, and the private 9850x3d-rdna4 studio room was listed here.
 *
 * Backend-free: the launcher reads JSON from disk inside the Next server. The
 * browser is cut off from everything else (other origins aborted, /api/*
 * answered 503), so the result does not depend on Supabase or any service.
 *
 * Run on its own:  npm run test:e2e:launcher
 *   (playwright.launcher.config.ts: real catalog + negative fixture catalog)
 * Under the default playwright.config.ts only the real-catalog test runs; the
 * fixture test needs the fixture server and skips itself.
 */

type AccessBlock = {
  visibility?: string;
  owner_only?: boolean;
  exclude_from_public_catalog?: boolean;
};

type CatalogRoom = { room_id: string; access?: AccessBlock };

const DEFAULT_REAL_ROOM_DIR = path.resolve(__dirname, '..', '..', 'config', 'rooms');

/** Pinned: the public set today. A change here must be a deliberate edit. */
const PINNED_PUBLIC_REAL = [
  'demo.room.rehearsal',
  'fordham.room.community',
  'persona.room.livingdoc',
  'tokenism.room.exchange',
];
const MUST_NOT_RENDER_REAL = ['darkxsides.room', '9850x3d-rdna4.room.studio'];
const PINNED_PUBLIC_FIXTURE = ['fixture.room.public'];

function readJson<T>(file: string): T {
  return JSON.parse(readFileSync(file, 'utf8').replace(/^﻿/, '')) as T;
}

/** Read every manifest the catalog names (the same set the loader reads). */
function readCatalog(roomDir: string): CatalogRoom[] {
  const catalog = readJson<{ rooms: Array<{ room_id: string; manifest: string }> }>(
    path.join(roomDir, 'catalog.json')
  );
  return catalog.rooms.map((entry) => {
    const manifest = readJson<{ room_id: string; access?: AccessBlock }>(path.join(roomDir, entry.manifest));
    return { room_id: manifest.room_id, access: manifest.access };
  });
}

/**
 * The contract, restated independently of lib/rooms.ts: public only on an
 * explicit visibility 'public'. Deliberately not imported from the code under test.
 */
function expectedPublicIds(rooms: CatalogRoom[]): string[] {
  return rooms
    .filter(
      (room) =>
        room.access?.visibility === 'public' &&
        room.access.owner_only !== true &&
        room.access.exclude_from_public_catalog !== true
    )
    .map((room) => room.room_id)
    .sort();
}

function catalogFor(testInfo: TestInfo): 'real' | 'fixture' | undefined {
  return testInfo.project.metadata?.launcherCatalog as 'real' | 'fixture' | undefined;
}

function roomDirFor(testInfo: TestInfo, fallback: string): string {
  return (testInfo.project.metadata?.roomDir as string | undefined) ?? fallback;
}

/** No backend: abort other origins, answer every /api/* with 503. */
async function isolateFromBackend(page: Page, baseURL: string): Promise<string[]> {
  const origin = new URL(baseURL).origin;
  const blocked: string[] = [];
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      blocked.push(url.href);
      return route.abort();
    }
    if (url.pathname.startsWith('/api/')) {
      blocked.push(url.pathname);
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'backend disabled in launcher-visibility e2e' }),
      });
    }
    return route.continue();
  });
  return blocked;
}

async function renderedRoomIds(page: Page): Promise<string[]> {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('home-room-launcher')).toBeVisible();
  const ids = await page
    .getByTestId('home-room-option')
    .evaluateAll((elements) => elements.map((element) => element.getAttribute('data-room-id') ?? ''));
  return ids.sort();
}

/**
 * The launcher options are serialized into the server-rendered HTML (RSC
 * payload) too. A room that is filtered only in the browser would still leak
 * there, so check the raw document as well as the DOM.
 */
async function rawHomeHtml(page: Page): Promise<string> {
  const response = await page.request.get('/');
  expect(response.status()).toBe(200);
  return response.text();
}

test.describe('@launcher-visibility public room launcher (unauthenticated home page)', () => {
  test('real catalog: renders exactly the explicitly public rooms', async ({ page, baseURL }, testInfo) => {
    test.skip(catalogFor(testInfo) === 'fixture', 'real-catalog assertions do not apply to the fixture server');

    const roomDir = roomDirFor(testInfo, DEFAULT_REAL_ROOM_DIR);
    const catalog = readCatalog(roomDir);
    const expected = expectedPublicIds(catalog);
    const hidden = catalog.map((room) => room.room_id).filter((id) => !expected.includes(id));

    // Derived from the manifests AND pinned: a manifest edit that widens or
    // narrows the public set must also edit this list.
    expect(expected).toEqual([...PINNED_PUBLIC_REAL].sort());
    for (const id of MUST_NOT_RENDER_REAL) {
      expect(hidden, `${id} must be in the catalog and not public`).toContain(id);
    }

    await isolateFromBackend(page, baseURL!);
    const rendered = await renderedRoomIds(page);
    expect(rendered).toEqual(expected);

    for (const id of MUST_NOT_RENDER_REAL) {
      await expect(page.locator(`[data-room-id="${id}"]`)).toHaveCount(0);
    }

    const html = await rawHomeHtml(page);
    // Positive control for the leak check: the public ids ARE visible in the raw HTML.
    for (const id of expected) expect(html).toContain(id);
    for (const id of hidden) {
      expect(html, `non-public room ${id} leaked into the home page HTML`).not.toContain(id);
    }
  });

  test('negative fixture: only the proper public room renders', async ({ page, baseURL }, testInfo) => {
    test.skip(
      catalogFor(testInfo) !== 'fixture',
      'needs the fixture-catalog server: npm run test:e2e:launcher'
    );

    const roomDir = roomDirFor(testInfo, '');
    const catalog = readCatalog(roomDir);
    const expected = expectedPublicIds(catalog);
    const hidden = catalog.map((room) => room.room_id).filter((id) => !expected.includes(id));

    expect(expected).toEqual(PINNED_PUBLIC_FIXTURE);
    // no access block, empty access, misspelled visibility, owner_only public
    expect(hidden.sort()).toEqual([
      'fixture.room.emptyaccess',
      'fixture.room.noaccess',
      'fixture.room.owneronly',
      'fixture.room.typo',
    ]);

    await isolateFromBackend(page, baseURL!);
    const rendered = await renderedRoomIds(page);
    expect(rendered).toEqual(PINNED_PUBLIC_FIXTURE);

    const html = await rawHomeHtml(page);
    for (const id of expected) expect(html).toContain(id);
    for (const id of hidden) {
      expect(html, `non-public fixture room ${id} leaked into the home page HTML`).not.toContain(id);
    }
  });
});
