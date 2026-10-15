const CANONICAL_HOST = "tserenov.com";
const ALIAS_HOSTS = new Set(["www.tserenov.com", "tserenov-com.pages.dev"]);

export function onRequest({ request, next }) {
  const url = new URL(request.url);
  if (!ALIAS_HOSTS.has(url.hostname)) return next();

  url.protocol = "https:";
  url.hostname = CANONICAL_HOST;
  return Response.redirect(url.toString(), 301);
}
