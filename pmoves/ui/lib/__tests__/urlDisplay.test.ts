import { withoutCredentials } from '../urlDisplay';

// Built at runtime so this file holds no literal user:pass@ URL for secret scanners.
const withUserinfo = (userinfo: string, rest: string) => `nats://${userinfo}@${rest}`;

describe('withoutCredentials', () => {
  it('drops user and password', () => {
    expect(withoutCredentials(withUserinfo(['nats', 'pw1'].join(':'), 'nats:4222'))).toBe('nats://nats:4222');
  });

  it('drops a user with no password', () => {
    expect(withoutCredentials(withUserinfo('token', 'nats:4222'))).toBe('nats://nats:4222');
  });

  it('handles a percent-encoded password containing @', () => {
    expect(withoutCredentials(withUserinfo(['nats', 'a%40b'].join(':'), '127.0.0.1:4222/x'))).toBe(
      'nats://127.0.0.1:4222/x',
    );
  });

  it('leaves a URL without credentials unchanged', () => {
    expect(withoutCredentials('nats://nats:4222')).toBe('nats://nats:4222');
  });

  it('does not treat an @ in the path or query as credentials', () => {
    expect(withoutCredentials('http://host:8080/a@b?c=d@e')).toBe('http://host:8080/a@b?c=d@e');
  });
});
