-- Pandoc custom writer: report the effective title, author, first level-1
-- heading and all image sources of a document as JSON.
local stringify = pandoc.utils.stringify

local function text(value)
  if value == nil then return nil end
  if pandoc.utils.type(value) == "List" then
    return table.concat(value:map(stringify), ", ")
  end
  return stringify(value)
end

function Writer(doc, opts)
  local images, heading = {}, nil
  doc:walk {
    Image = function(img) table.insert(images, img.src) end,
    Header = function(h)
      if h.level == 1 and heading == nil then heading = stringify(h) end
    end,
  }
  return pandoc.json.encode {
    title = text(doc.meta.title),
    author = text(doc.meta.author),
    heading = heading,
    images = images,
  }
end
