/**
 * Idempotent Discord server setup from channel-structure.yaml.
 * Creates categories, channels, roles, and webhooks.
 * Safe to re-run — skips existing resources.
 */
const { Client, GatewayIntentBits, PermissionFlagsBits, ChannelType } = require('discord.js');
const { loadConfig } = require('./config');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const GUILD_ID = process.env.DISCORD_GUILD_ID;

if (!TOKEN || !GUILD_ID) {
  console.error('Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID environment variables');
  process.exit(1);
}

const PERMISSION_MAP = {
  Administrator: PermissionFlagsBits.Administrator,
  ManageChannels: PermissionFlagsBits.ManageChannels,
  ManageMessages: PermissionFlagsBits.ManageMessages,
  MoveMembers: PermissionFlagsBits.MoveMembers,
  MuteMembers: PermissionFlagsBits.MuteMembers,
  SendMessages: PermissionFlagsBits.SendMessages,
  ReadMessageHistory: PermissionFlagsBits.ReadMessageHistory,
  Connect: PermissionFlagsBits.Connect,
  Speak: PermissionFlagsBits.Speak,
  AttachFiles: PermissionFlagsBits.AttachFiles,
};

async function main() {
  const config = loadConfig();
  const client = new Client({ intents: [GatewayIntentBits.Guilds] });

  await client.login(TOKEN);
  console.log(`Logged in as ${client.user.tag}`);

  const guild = await client.guilds.fetch(GUILD_ID);
  console.log(`Guild: ${guild.name} (${guild.id})`);

  // --- Roles ---
  console.log('\n--- Roles ---');
  const createdRoles = {};
  for (const roleDef of config.roles || []) {
    let role = guild.roles.cache.find(r => r.name === roleDef.name);
    if (role) {
      console.log(`  [exists] ${roleDef.name} (${role.id})`);
    } else {
      const perms = (roleDef.permissions || []).reduce((acc, p) => {
        if (PERMISSION_MAP[p]) acc |= PERMISSION_MAP[p];
        return acc;
      }, 0n);
      role = await guild.roles.create({
        name: roleDef.name,
        color: roleDef.color || null,
        hoist: roleDef.hoist || false,
        permissions: perms,
        reason: 'PMOVES Discord Bot setup',
      });
      console.log(`  [created] ${roleDef.name} (${role.id})`);
    }
    createdRoles[roleDef.name] = role;
  }

  // --- Categories + Channels ---
  console.log('\n--- Categories & Channels ---');
  const webhookUrls = {};

  for (const catDef of config.categories || []) {
    // Find or create category
    let category = guild.channels.cache.find(
      c => c.type === ChannelType.GuildCategory && c.name.toUpperCase() === catDef.name.toUpperCase()
    );
    if (!category) {
      category = await guild.channels.create({
        name: catDef.name,
        type: ChannelType.GuildCategory,
        reason: 'PMOVES Discord Bot setup',
      });
      console.log(`  [created] Category: ${catDef.name}`);
    } else {
      console.log(`  [exists] Category: ${catDef.name}`);
    }

    // Channels in category
    for (const chDef of catDef.channels || []) {
      const channelType = chDef.type === 'voice' ? ChannelType.GuildVoice : ChannelType.GuildText;
      let channel = guild.channels.cache.find(
        c => c.name === chDef.name && c.parentId === category.id
      );
      if (!channel) {
        channel = await guild.channels.create({
          name: chDef.name,
          type: channelType,
          parent: category.id,
          topic: chDef.topic || null,
          reason: 'PMOVES Discord Bot setup',
        });
        console.log(`    [created] #${chDef.name} (${channelType === ChannelType.GuildVoice ? 'voice' : 'text'})`);
      } else {
        console.log(`    [exists] #${chDef.name}`);
      }

      // Create webhook if needed
      if (chDef.webhook && channelType === ChannelType.GuildText) {
        const webhooks = await channel.fetchWebhooks();
        let webhook = webhooks.find(w => w.name === 'PMOVES Publisher');
        if (!webhook) {
          webhook = await channel.createWebhook({
            name: 'PMOVES Publisher',
            reason: 'PMOVES Discord Bot — event routing',
          });
          console.log(`    [webhook] Created for #${chDef.name}: ${webhook.url.substring(0, 60)}...`);
        } else {
          console.log(`    [webhook] Exists for #${chDef.name}`);
        }
        webhookUrls[chDef.name] = {
          url: webhook.url,
          channel_id: channel.id,
          nats_subjects: chDef.nats_subjects || [],
        };
      }
    }
  }

  // --- Output webhook mapping ---
  console.log('\n--- Webhook Routing Map ---');
  console.log(JSON.stringify(webhookUrls, null, 2));

  console.log('\nSetup complete.');
  client.destroy();
  process.exit(0);
}

main().catch(err => {
  console.error('Setup failed:', err);
  process.exit(1);
});
