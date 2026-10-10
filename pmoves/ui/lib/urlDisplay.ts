/**
 * Reduce a URL to scheme, host, port and path before it is shown anywhere.
 *
 * Service URLs such as NATS_URL carry their credential inline
 * (nats://user:password@host:4222), and others carry one in the query
 * (?token=...). A server component that renders one still ships it to the
 * browser in the HTML, so userinfo, query and fragment are all dropped.
 * Userinfo goes first: a raw '?' or '#' inside a password would otherwise cut
 * the URL mid-credential and leave the start of it on the page.
 */
export function withoutCredentials(url: string): string {
  return url
    .replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/]*@/i, '$1')
    .replace(/[?#].*$/, '');
}
