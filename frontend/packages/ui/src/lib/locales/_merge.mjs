import { readFileSync, writeFileSync } from 'fs';

const existing = JSON.parse(readFileSync('/home/franpv2004/proyecto/lamb/frontend/packages/ui/src/lib/locales/ca.json', 'utf8'));

const incoming = JSON.parse(readFileSync('/home/franpv2004/proyecto/lamb/frontend/packages/ui/src/lib/locales/_incoming_ca.json', 'utf8'));

function deepMerge(target, source) {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (
      typeof source[key] === 'object' &&
      source[key] !== null &&
      !Array.isArray(source[key]) &&
      typeof result[key] === 'object' &&
      result[key] !== null &&
      !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(result[key], source[key]);
    } else {
      // incoming wins (overwrite or add)
      result[key] = source[key];
    }
  }
  return result;
}

const merged = deepMerge(existing, incoming);
writeFileSync('/home/franpv2004/proyecto/lamb/frontend/packages/ui/src/lib/locales/ca.json', JSON.stringify(merged, null, 2) + '\n', 'utf8');

// Report stats
function countKeys(obj, prefix = '') {
  let count = 0;
  for (const key of Object.keys(obj)) {
    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      count += countKeys(obj[key], prefix + key + '.');
    } else {
      count++;
    }
  }
  return count;
}

console.log(`Existing keys: ${countKeys(existing)}`);
console.log(`Incoming keys: ${countKeys(incoming)}`);
console.log(`Merged keys:   ${countKeys(merged)}`);
console.log('Merge complete!');
