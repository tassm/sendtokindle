-- Pandoc filter: replace images listed in SENDTOKINDLE_BLOCKED_IMAGES (a JSON
-- array of sources) with their alt text, so they are never fetched or embedded.
local blocked = {}
for _, src in ipairs(pandoc.json.decode(os.getenv("SENDTOKINDLE_BLOCKED_IMAGES") or "[]")) do
  blocked[src] = true
end

function Image(img)
  if blocked[img.src] then return img.caption end
end
