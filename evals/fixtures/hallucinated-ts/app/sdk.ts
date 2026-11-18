export interface Payment {
  amount: number;
  currency: string;
}

export function createPayment(amount: number, currency = "usd"): Payment {
  return { amount, currency };
}
