export function generateKeysString(keys) {
  let keysString = [];
  const setKeys = new Set(keys.map((e) => e.toLowerCase()));
  if (setKeys.has("ctrl")) {
    keysString.push("ctrl");
    setKeys.delete("ctrl");
  }
  if (setKeys.has("shift")) {
    keysString.push("shift");
    setKeys.delete("shift");
  }
  setKeys.forEach((key) => {
    keysString.push(key);
  });

  return keysString.join("+");
}
