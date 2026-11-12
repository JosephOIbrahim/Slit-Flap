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

// One in-flight write per note. The content is captured when save() is called,
// but the version is read by putNote only when that save reaches the front of
// the queue, so it always includes the version returned by the previous save.
export function createNotesSaveQueue({ getDraft, getNote, putNote, onVersion, onConflict, onSaved }) {
  let chain = Promise.resolve();

  const write = async (content, keepalive, isReplay) => {
    try {
      const saved = await putNote(content, keepalive);
      if (saved && saved.updatedAt) onVersion(saved.updatedAt);
      if (onSaved) onSaved(saved);
    } catch (err) {
      if (!err || err.status !== 409) return;

      // The server supplies a fresh base version, never replacement editor
      // content. Read the draft now: it may be newer than the failed snapshot.
      const latest = await getNote().catch(() => null);
      if (latest && latest.updatedAt) onVersion(latest.updatedAt);
      if (onConflict) onConflict(latest);
      if (!latest || isReplay) return;
      await write(getDraft(), keepalive, true);
    }
  };

  const save = (content, { keepalive = false } = {}) => {
    const result = chain.then(() => write(content, keepalive, false));
    chain = result.catch(() => {});
    return result;
  };

  return { save, idle: () => chain };
}

