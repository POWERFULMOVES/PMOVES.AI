import { promises as fs } from 'node:fs';
import path from 'node:path';

export interface RoomCatalogEntry {
  room_id: string;
  agent_id: string;
  alter?: string;
  display_name: string;
  manifest: string;
  summary?: string;
}

export interface RoomCatalog {
  schema_version: string;
  rooms: RoomCatalogEntry[];
}

export interface RoomPanel {
  panel_id: string;
  kind: string;
  position: string;
  size?: number;
  pinned?: boolean;
}

export interface RoomApp {
  app_id: string;
  kind: string;
  route: string;
  provider?: string;
  action_namespace?: string;
  capabilities: string[];
  pinned?: boolean;
}

export interface RoomSkillBinding {
  binding_id: string;
  display_name: string;
  intent: string[];
  enabled?: boolean;
  tags?: string[];
  surface?: {
    app_id: string;
    target?: string;
    route?: string;
  };
  execution?: {
    mode?: string;
    run_as?: string;
    stream?: string;
    max_steps?: number;
  };
}

export interface RoomManifest {
  room_id: string;
  version: string;
  display_name: string;
  description?: string;
  agent_id: string;
  alter?: string;
  room_type?: string;
  owner_mode?: string;
  shell: {
    theme: {
      theme_id: string;
      accent_color?: string;
      skin?: string;
      icon?: string;
    };
    layout: {
      default_route: string;
      panels: RoomPanel[];
    };
  };
  apps: RoomApp[];
  notebook: {
    provider: string;
    workspace_ref: string;
    thread_ref?: string;
    default_page?: string;
    sync: {
      mode: string;
      writeback_targets: string[];
      artifact_prefix?: string;
    };
  };
  persona?: {
    signature_ref?: string;
    voice?: string;
    glyph?: string;
    resonance?: string[];
  };
  skill_bindings: RoomSkillBinding[];
  policies: {
    model_routing: string;
    publish: {
      allow_nats_emit: boolean;
      allow_external_publish: boolean;
      allowed_subjects?: string[];
    };
    memory: {
      graphiti: boolean;
      notebook_writeback: boolean;
      chit_handoff: boolean;
    };
  };
  telemetry?: {
    graphiti_phase?: string;
    room_events_subject?: string;
    healthcheck_route?: string;
  };
  provenance?: {
    source: string;
    updated_at: string;
    related_docs?: string[];
  };
}

export interface RoomDefinition extends Omit<RoomCatalogEntry, 'manifest'> {
  manifestFile: string;
  manifestPath: string;
  manifest: RoomManifest;
}

const DEFAULT_ROOM_CONFIG_DIR = process.env.PMOVES_ROOM_CONFIG_DIR
  ? path.resolve(process.env.PMOVES_ROOM_CONFIG_DIR)
  : path.resolve(process.cwd(), '..', 'config', 'rooms');

function stripBom(raw: string): string {
  return raw.replace(/^\uFEFF/, '');
}

async function readJsonFile<T>(filePath: string): Promise<T> {
  const raw = await fs.readFile(filePath, 'utf8');
  return JSON.parse(stripBom(raw)) as T;
}

function validateCatalogParity(entry: RoomCatalogEntry, manifest: RoomManifest): void {
  if (manifest.room_id !== entry.room_id) {
    throw new Error(`Room manifest mismatch for ${entry.manifest}: room_id ${manifest.room_id} !== ${entry.room_id}`);
  }

  if (manifest.agent_id !== entry.agent_id) {
    throw new Error(`Room manifest mismatch for ${entry.manifest}: agent_id ${manifest.agent_id} !== ${entry.agent_id}`);
  }

  if ((manifest.alter ?? '') !== (entry.alter ?? '')) {
    throw new Error(`Room manifest mismatch for ${entry.manifest}: alter ${manifest.alter ?? ''} !== ${entry.alter ?? ''}`);
  }

  if (manifest.display_name !== entry.display_name) {
    throw new Error(`Room manifest mismatch for ${entry.manifest}: display_name ${manifest.display_name} !== ${entry.display_name}`);
  }
}

export function getRoomConfigDir(): string {
  return DEFAULT_ROOM_CONFIG_DIR;
}

export async function loadRoomCatalog(roomConfigDir = DEFAULT_ROOM_CONFIG_DIR): Promise<RoomCatalog> {
  return readJsonFile<RoomCatalog>(path.join(roomConfigDir, 'catalog.json'));
}

export async function loadRooms(roomConfigDir = DEFAULT_ROOM_CONFIG_DIR): Promise<RoomDefinition[]> {
  const catalog = await loadRoomCatalog(roomConfigDir);
  const rooms = await Promise.all(
    catalog.rooms.map(async (entry) => {
      const manifestPath = path.join(roomConfigDir, entry.manifest);
      const manifest = await readJsonFile<RoomManifest>(manifestPath);
      validateCatalogParity(entry, manifest);
      return {
        ...entry,
        manifestFile: entry.manifest,
        manifestPath,
        manifest,
      } satisfies RoomDefinition;
    })
  );

  return rooms.sort((left, right) => left.display_name.localeCompare(right.display_name));
}

export async function loadRoom(roomId: string, roomConfigDir = DEFAULT_ROOM_CONFIG_DIR): Promise<RoomDefinition | null> {
  const rooms = await loadRooms(roomConfigDir);
  return rooms.find((room) => room.room_id === roomId) ?? null;
}


