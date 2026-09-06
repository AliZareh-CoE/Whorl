/** Classic URL → SPA route mapping — shared by the command bar and the global
 * link interceptor so in-app navigation never full-reloads when a SPA page exists. */
export function toSpaUrl(url: string): { to: string; spa: boolean } {
  const maps: [RegExp, (m: RegExpMatchArray) => string][] = [
    [/^\/$/, () => "/"],
    [/^\/projects\/new\/?$/, () => "/projects/new"],
    [/^\/projects\/$/, () => "/projects"],
    [/^\/projects\/([^/]+)\/$/, (m) => `/projects/${m[1]}`],
    [/^\/projects\/([^/]+)\/(plan|documents|figures|literature|research|decisions|graph)\/$/, (m) => `/projects/${m[1]}/${m[2]}`],
    [/^\/projects\/([^/]+)\/literature\/queue\/$/, (m) => `/projects/${m[1]}/queue`],
    [/^\/projects\/([^/]+)\/notes\/$/, (m) => `/projects/${m[1]}/notes`],
    [/^\/projects\/([^/]+)\/notes\/(\d+)\/$/, (m) => `/projects/${m[1]}/notes/${m[2]}`],
    [/^\/projects\/([^/]+)\/(timeline|files)\/$/, (m) => `/projects/${m[1]}/${m[2]}`],
    [/^\/projects\/([^/]+)\/writing\/$/, () => "/writing"],
    [/^\/projects\/([^/]+)\/writing\/(\d+)\/$/, (m) => `/manuscripts/${m[2]}`],
    [/^\/projects\/([^/]+)\/writing\/(\d+)\/editor\/$/, (m) => `/manuscripts/${m[2]}/editor`],
    [/^\/library\/(\d+)\/$/, (m) => `/references/${m[1]}`],
    [/^\/library\/$/, () => "/library"],
    [/^\/writing\/$/, () => "/writing"],
    [/^\/inbox\/$/, () => "/inbox"],
    [/^\/today\/?$/, () => "/today"],
    [/^\/prompts\/$/, () => "/prompts"],
    [/^\/search\/$/, () => "/search"],
    [/^\/automations\/$/, () => "/automations"],
  ];
  for (const [re, build] of maps) {
    const m = url.match(re);
    if (m) return { to: build(m), spa: true };
  }
  return { to: url, spa: false };
}
