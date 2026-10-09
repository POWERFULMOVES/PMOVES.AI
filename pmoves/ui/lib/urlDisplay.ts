/**
 * Drop the user:password part of a URL before it is shown anywhere.
 *
 * Service URLs such as NATS_URL carry their credential inline
 * (nats://user:password@host:4222). A server component that renders one still
 * ships it to the browser in the HTML, so anything displayed keeps only the
 * scheme, host, port and path.
 */
export function withoutCredentials(url: string): string {
  return url.replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/?#]*@/i, '$1');
}
