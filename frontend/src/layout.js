// Layout arithmetic kept free of React so the phone rules are testable.

export const PHONE_WIDTH = 600;

export function isPhoneWidth(width) {
  return width <= PHONE_WIDTH;
}

// How large a split-flap character can be and still fit `text` across a card.
// A module is 0.7 x size wide with a 4px gap between modules.
export function flapSizeFor({ width, text, preferred = 104, min = 24 }) {
  const usable = Math.max(0, width - 72);  // 12px page gutters + 24px card padding each side
  const letters = Math.max(1, (text || "").length);
  const fit = Math.floor((usable - 4 * (letters - 1)) / (letters * 0.7));
  return Math.max(min, Math.min(preferred, fit));
}
