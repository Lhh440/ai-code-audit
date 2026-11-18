import { createPayment, createCharge } from "./sdk";
import stripeHelper from "./sdk";
import { parseMoney } from "./money";

export function pay(total: number) {
  return createCharge(total);
}

export function payViaHelper(total: number) {
  return stripeHelper(total);
}

export function payParsed(raw: string) {
  return createPayment(parseMoney(raw));
}
