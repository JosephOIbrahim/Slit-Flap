// Notes-save rules, kept free of React so they can be tested with `npm test`.

// Nothing may be written back until the stored note has loaded: an empty
// editor saving over a real note is how a thought gets lost.
export function canSaveNotes(loadState, readOnly) {
  return !readOnly && loadState === "ready";
}

// Paste keeps words, not the source page's fonts, colours or links.
export function plainTextFrom(clipboard) {
  return (clipboard && typeof clipboard.getData === "function"
    && clipboard.getData("text/plain")) || "";
}
