/**
 * PMOVES Discord Bot — CATACLYSM STUDIOS INC community playground.
 * Connects to Discord gateway, listens for events, routes to PMOVES services.
 */
const { Client, GatewayIntentBits, Events } = require('discord.js');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const GUILD_ID = process.env.DISCORD_GUILD_ID;

if (!TOKEN) {
  console.error('Set DISCORD_BOT_TOKEN environment variable');
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildVoiceStates,
  ],
});

client.once(Events.ClientReady, (c) => {
  // This line is captured by start.js event regex
  console.log(`Bot ready as ${c.user.tag}`);
  console.log(`Guilds: ${c.guilds.cache.map(g => g.name).join(', ')}`);
});

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;

  // !ask command — route to Hi-RAG
  if (message.content.startsWith('!ask ')) {
    const query = message.content.slice(5).trim();
    if (!query) return;
    try {
      const resp = await fetch('http://host.docker.internal:8086/hirag/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 5, rerank: true }),
      });
      const data = await resp.json();
      const results = (data.results || []).slice(0, 3);
      if (results.length === 0) {
        await message.reply('No results found.');
        return;
      }
      const formatted = results.map((r, i) =>
        `**${i + 1}.** ${r.text?.substring(0, 200) || 'No text'}...`
      ).join('\n\n');
      await message.reply(formatted);
    } catch (err) {
      await message.reply(`Search error: ${err.message}`);
    }
  }

  // !voice command — route to Flute-Gateway TTS
  if (message.content.startsWith('!voice ')) {
    const text = message.content.slice(7).trim();
    if (!text) return;
    try {
      const resp = await fetch('http://host.docker.internal:8055/v1/voice/synthesize/audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, intent: 'narrate' }),
      });
      if (!resp.ok) {
        await message.reply(`TTS error: ${resp.status}`);
        return;
      }
      const buffer = Buffer.from(await resp.arrayBuffer());
      await message.reply({
        files: [{ attachment: buffer, name: 'voice.wav' }],
      });
    } catch (err) {
      await message.reply(`Voice error: ${err.message}`);
    }
  }
});

client.on(Events.GuildMemberAdd, async (member) => {
  // Auto-assign Student role on join
  try {
    const studentRole = member.guild.roles.cache.find(r => r.name === 'Student');
    if (studentRole) {
      await member.roles.add(studentRole);
      console.log(`Assigned Student role to ${member.user.tag}`);
    }
  } catch (err) {
    console.error(`Failed to assign role: ${err.message}`);
  }
});

client.login(TOKEN);
