package sdk

type Payment struct {
	Amount   int
	Currency string
}

func CreatePayment(amount int, currency string) Payment {
	return Payment{Amount: amount, Currency: currency}
}

func Total(payments []Payment) int {
	total := 0
	for _, payment := range payments {
		total += payment.Amount
	}
	return total
}
