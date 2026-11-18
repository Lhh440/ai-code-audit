package sdk

type Payment struct {
	Amount   int
	Currency string
}

func CreatePayment(amount int, currency string) Payment {
	return Payment{Amount: amount, Currency: currency}
}

func helper() {}
