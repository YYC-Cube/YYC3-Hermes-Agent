import { normalizeLocale, type Locale as PackageLocale } from "@yyc3/i18n-core/browser";
import type { Locale } from "./types";

/** Package locale (10) → app locale (17): zh and pt app locales are regional
 *  aliases of the package set (zh-CN/zh-TW/pt-BR). */
const PACKAGE_TO_APP: Record<PackageLocale, Locale> = {
  en: "en",
  "zh-CN": "zh",
  "zh-TW": "zh-hant",
  ja: "ja",
  ko: "ko",
  fr: "fr",
  de: "de",
  es: "es",
  "pt-BR": "pt",
  ar: "ar",
};

// App locales the package does not know, matched by BCP-47 primary tag.
const EXTRA_PRIMARY = new Set<string>(["tr", "uk", "af", "it", "ga", "ru", "hu"]);
// Traditional-Chinese tags the package would normalize to zh-CN — checked first.
const HANT_TAGS = new Set(["zh-hant", "zh-tw", "zh-hk", "zh-mo"]);

function matchLocaleTag(tag: string): Locale | null {
  const lower = tag.toLowerCase();
  if (HANT_TAGS.has(lower) || lower.startsWith("zh-hant")) return "zh-hant";
  const normalized = normalizeLocale(tag);
  if (normalized) return PACKAGE_TO_APP[normalized];
  const primary = lower.split(/[-_]/)[0];
  return EXTRA_PRIMARY.has(primary) ? (primary as Locale) : null;
}

/** Best-effort system-language detection for first visits: navigator.languages →
 *  package normalization (en/zh/ja/ko/fr/de/es/pt/ar) → extra primary tags → en. */
export function detectSystemAppLocale(): Locale {
  if (typeof navigator === "undefined") return "en";
  for (const tag of navigator.languages ?? (navigator.language ? [navigator.language] : [])) {
    const matched = matchLocaleTag(tag);
    if (matched) return matched;
  }
  return "en";
}
