import { getRoomConfigDir, loadRoom, loadRoomCatalog, loadRooms } from '../rooms';

describe('room catalog loader', () => {
  it('resolves the seeded room catalog directory', () => {
    expect(getRoomConfigDir().replace(/\\/g, '/')).toMatch(/pmoves\/config\/rooms$/);
  });

  it('loads the room catalog entries', async () => {
    const catalog = await loadRoomCatalog();
    expect(catalog.schema_version).toBe('1.0.0');
    expect(catalog.rooms.map((room) => room.room_id)).toEqual(
      expect.arrayContaining([
        '4090-field.room.control',
        '5090-voice.room.studio',
        'z890-infra.room.fabric',
      ])
    );
  });

  it('hydrates room manifests with catalog parity checks', async () => {
    const rooms = await loadRooms();
    const fieldRoom = rooms.find((room) => room.room_id === '4090-field.room.control');

    expect(fieldRoom).toBeDefined();
    expect(fieldRoom?.manifest.shell.layout.default_route).toBe('/dashboard/notebook/runtime');
    expect(fieldRoom?.manifest.apps.some((app) => app.pinned)).toBe(true);
    expect(fieldRoom?.manifest.skill_bindings.length).toBeGreaterThan(0);
  });

  it('loads a single room by id', async () => {
    const voiceRoom = await loadRoom('5090-voice.room.studio');

    expect(voiceRoom?.agent_id).toBe('5090-claude');
    expect(voiceRoom?.manifest.notebook.provider).toBe('open-notebook');
    expect(voiceRoom?.manifest.policies.model_routing).toBe('hybrid');
  });

  it('returns null for unknown rooms', async () => {
    await expect(loadRoom('missing-room')).resolves.toBeNull();
  });
});
