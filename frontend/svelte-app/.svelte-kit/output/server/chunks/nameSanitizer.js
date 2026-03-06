function sanitizeName(name, maxLength = 50) {
  if (!name) {
    return { sanitized: "", wasModified: false };
  }
  const originalName = name;
  name = name.trim();
  name = name.toLowerCase();
  name = name.replace(/\s+/g, "_");
  name = name.replace(/[^a-z0-9_]/g, "");
  name = name.replace(/_+/g, "_");
  name = name.replace(/^_+|_+$/g, "");
  if (name.length > maxLength) {
    name = name.substring(0, maxLength);
    name = name.replace(/_+$/, "");
  }
  if (!name) {
    name = "untitled";
  }
  const wasModified = name !== originalName.trim().toLowerCase() && originalName.trim() !== "";
  return {
    sanitized: name,
    wasModified
  };
}
export {
  sanitizeName as s
};
