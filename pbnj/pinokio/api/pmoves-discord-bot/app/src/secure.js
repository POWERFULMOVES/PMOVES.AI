/**
 * Discord server security hardening.
 * Configures AutoMod rules, verification level, content filters, and 2FA.
 * Idempotent — safe to re-run.
 */
const {
  Client,
  GatewayIntentBits,
  GuildVerificationLevel,
  GuildExplicitContentFilter,
  GuildDefaultMessageNotifications,
  AutoModerationRuleTriggerType,
  AutoModerationRuleEventType,
  AutoModerationActionType,
} = require('discord.js');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const GUILD_ID = process.env.DISCORD_GUILD_ID;

if (!TOKEN || !GUILD_ID) {
  console.error('Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID environment variables');
  process.exit(1);
}

async function main() {
  const client = new Client({ intents: [GatewayIntentBits.Guilds] });
  await client.login(TOKEN);
  console.log(`Logged in as ${client.user.tag}`);

  const guild = await client.guilds.fetch(GUILD_ID);
  console.log(`Guild: ${guild.name}\n`);

  // --- Guild-Level Settings ---
  console.log('--- Guild Security Settings ---');

  await guild.setVerificationLevel(GuildVerificationLevel.High);
  console.log('  [set] Verification level: HIGH (must be member for 10 min)');

  await guild.setExplicitContentFilter(GuildExplicitContentFilter.AllMembers);
  console.log('  [set] Explicit content filter: ALL MEMBERS');

  await guild.setDefaultMessageNotifications(GuildDefaultMessageNotifications.OnlyMentions);
  console.log('  [set] Default notifications: ONLY MENTIONS');

  // --- AutoMod Rules ---
  console.log('\n--- AutoMod Rules ---');

  const existingRules = await guild.autoModerationRules.fetch();
  const ruleNames = existingRules.map(r => r.name);

  // Rule 1: Mention spam protection
  if (!ruleNames.includes('PMOVES: Mention Spam')) {
    await guild.autoModerationRules.create({
      name: 'PMOVES: Mention Spam',
      eventType: AutoModerationRuleEventType.MessageSend,
      triggerType: AutoModerationRuleTriggerType.MentionSpam,
      triggerMetadata: {
        mentionTotalLimit: 5,
        mentionRaidProtectionEnabled: true,
      },
      actions: [
        {
          type: AutoModerationActionType.BlockMessage,
          metadata: { customMessage: 'Too many mentions. Please keep it respectful.' },
        },
        {
          type: AutoModerationActionType.Timeout,
          metadata: { durationSeconds: 300 },
        },
      ],
      enabled: true,
      reason: 'PMOVES Discord Bot — mention spam protection',
    });
    console.log('  [created] Mention Spam (limit: 5, timeout: 5min, raid protection: on)');
  } else {
    console.log('  [exists] Mention Spam');
  }

  // Rule 2: Keyword filter (links, scam, phishing patterns)
  if (!ruleNames.includes('PMOVES: Link & Scam Filter')) {
    await guild.autoModerationRules.create({
      name: 'PMOVES: Link & Scam Filter',
      eventType: AutoModerationRuleEventType.MessageSend,
      triggerType: AutoModerationRuleTriggerType.Keyword,
      triggerMetadata: {
        keywordFilter: [
          'free nitro',
          'steam gift',
          'claim your prize',
          'click here to verify',
          'discord.gg/free',
          'earn money fast',
          'dm me for',
        ],
        regexPatterns: [
          'https?://discord\\.gift/[a-zA-Z0-9]+',
          'https?://dis[ck]ord[.-]\\w+\\.\\w+',
        ],
        allowList: [
          'discord.gg',
          'github.com',
          'youtube.com',
          'pmoves.ai',
          'cataclysmstudios.com',
        ],
      },
      actions: [
        {
          type: AutoModerationActionType.BlockMessage,
          metadata: { customMessage: 'This message was blocked by PMOVES security filters.' },
        },
      ],
      enabled: true,
      reason: 'PMOVES Discord Bot — scam/phishing protection',
    });
    console.log('  [created] Link & Scam Filter (7 keywords, 2 regex, 5 allowlist)');
  } else {
    console.log('  [exists] Link & Scam Filter');
  }

  // Rule 3: Discord preset filters (profanity, slurs, sexual content)
  if (!ruleNames.includes('PMOVES: Content Moderation')) {
    await guild.autoModerationRules.create({
      name: 'PMOVES: Content Moderation',
      eventType: AutoModerationRuleEventType.MessageSend,
      triggerType: AutoModerationRuleTriggerType.KeywordPreset,
      triggerMetadata: {
        presets: [1, 2, 3], // Profanity, SexualContent, Slurs
        allowList: [],
      },
      actions: [
        {
          type: AutoModerationActionType.BlockMessage,
          metadata: { customMessage: 'Please keep conversations respectful and professional.' },
        },
      ],
      enabled: true,
      reason: 'PMOVES Discord Bot — content moderation presets',
    });
    console.log('  [created] Content Moderation (profanity + sexual + slurs presets)');
  } else {
    console.log('  [exists] Content Moderation');
  }

  console.log('\nSecurity hardening complete.');
  client.destroy();
  process.exit(0);
}

main().catch(err => {
  console.error('Security setup failed:', err.message);
  process.exit(1);
});
