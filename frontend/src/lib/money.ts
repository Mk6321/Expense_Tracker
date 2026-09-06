import Decimal from "decimal.js";

/**
 * All client-side money maths goes through decimal.js. The API is the only
 * authority on balances -- this is for display-time arithmetic such as the live
 * "remaining to allocate" figure while someone types a custom split.
 */

Decimal.set({ precision: 28, rounding: Decimal.ROUND_HALF_UP });

export function d(value: string | number | Decimal | null | undefined): Decimal {
  if (value === null || value === undefined || value === "") return new Decimal(0);
  return new Decimal(value.toString());
}

export function toFixed(value: string | number | Decimal | null | undefined): string {
  return d(value).toFixed(2);
}

const SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
  AUD: "A$",
  CAD: "C$",
  SGD: "S$",
  AED: "د.إ",
};

export function symbolFor(currency: string): string {
  return SYMBOLS[currency?.toUpperCase()] ?? `${currency} `;
}

/** "1234.5" -> "₹1,234.50". Grouping is applied to the integer part only. */
export function formatMoney(
  value: string | number | Decimal | null | undefined,
  currency = "INR",
  options: { signed?: boolean; absolute?: boolean } = {},
): string {
  const amount = options.absolute ? d(value).abs() : d(value);
  const negative = amount.isNegative();
  const [whole, fraction] = amount.abs().toFixed(2).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  const sign = negative ? "-" : options.signed && !amount.isZero() ? "+" : "";
  return `${sign}${symbolFor(currency)}${grouped}.${fraction}`;
}

/** Compact form for tight spaces: 1234567 -> "₹1.23M". */
export function formatCompact(
  value: string | number | Decimal | null | undefined,
  currency = "INR",
): string {
  const amount = d(value).abs();
  const sign = d(value).isNegative() ? "-" : "";
  const units: [Decimal, string][] = [
    [new Decimal(1_000_000_000), "B"],
    [new Decimal(1_000_000), "M"],
    [new Decimal(1_000), "K"],
  ];
  for (const [threshold, suffix] of units) {
    if (amount.gte(threshold)) {
      return `${sign}${symbolFor(currency)}${amount.div(threshold).toFixed(2)}${suffix}`;
    }
  }
  return formatMoney(value, currency);
}

export function sum(values: (string | number | Decimal | null | undefined)[]): Decimal {
  return values.reduce<Decimal>((total, value) => total.plus(d(value)), new Decimal(0));
}

export function isZero(value: string | number | Decimal | null | undefined): boolean {
  return d(value).isZero();
}

export function isNegative(value: string | number | Decimal | null | undefined): boolean {
  return d(value).isNegative();
}

/**
 * Mirrors the backend's largest-remainder split so the "everyone pays X" preview
 * matches what actually gets saved. Display only -- the server always recomputes.
 */
export function previewEqualSplit(total: string, userIds: number[]): Map<number, string> {
  const result = new Map<number, string>();
  if (userIds.length === 0) return result;

  const totalCents = d(total).times(100).toDecimalPlaces(0, Decimal.ROUND_HALF_UP);
  const base = totalCents.div(userIds.length).floor();
  let leftover = totalCents.minus(base.times(userIds.length)).toNumber();

  // Ties everywhere, so the tiebreak is ascending user_id -- same rule as the server.
  const ordered = [...userIds].sort((a, b) => a - b);
  for (const userId of ordered) {
    const extra = leftover > 0 ? 1 : 0;
    if (leftover > 0) leftover -= 1;
    result.set(userId, base.plus(extra).div(100).toFixed(2));
  }
  return result;
}
