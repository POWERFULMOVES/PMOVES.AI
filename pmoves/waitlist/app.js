// PMOVES.AI Waitlist — Supabase Email Collection
// Uses ANON_KEY (safe for client-side, RLS protects reads)

const SUPABASE_URL = window.PMOVES_SUPABASE_URL || 'http://localhost:8000';
const SUPABASE_ANON_KEY = window.PMOVES_SUPABASE_ANON_KEY || '';

const form = document.getElementById('waitlist-form');
const feedback = document.getElementById('form-feedback');
const emailInput = document.getElementById('email-input');
const tierSelect = document.getElementById('tier-select');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = emailInput.value.trim();
  const tier = tierSelect.value;

  if (!email) return;

  const btn = form.querySelector('.cta-btn');
  btn.disabled = true;
  btn.textContent = 'Joining...';
  feedback.textContent = '';
  feedback.className = 'form-feedback';

  try {
    if (!SUPABASE_ANON_KEY) {
      // Fallback: no Supabase configured — show success with email-us message
      feedback.textContent = 'Waitlist coming soon! Email us at hello@pmoves.ai to join early.';
      feedback.className = 'form-feedback success';
      btn.textContent = 'Join the Waitlist';
      btn.disabled = false;
      return;
    }

    const response = await fetch(`${SUPABASE_URL}/rest/v1/waitlist_signups`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
        'Prefer': 'return=minimal',
      },
      body: JSON.stringify({
        email,
        tier_interest: tier,
        source: 'landing',
      }),
    });

    if (response.ok || response.status === 201) {
      feedback.textContent = "You're on the list! We'll be in touch.";
      feedback.className = 'form-feedback success';
      emailInput.value = '';
    } else if (response.status === 409) {
      feedback.textContent = "You're already on the list!";
      feedback.className = 'form-feedback success';
    } else {
      const errText = await response.text();
      if (errText.includes('duplicate') || errText.includes('unique')) {
        feedback.textContent = "You're already on the list!";
        feedback.className = 'form-feedback success';
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    }
  } catch (err) {
    feedback.textContent = 'Something went wrong. Email hello@pmoves.ai to join manually.';
    feedback.className = 'form-feedback error';
    console.error('Waitlist signup error:', err);
  } finally {
    btn.textContent = 'Join the Waitlist';
    btn.disabled = false;
  }
});
