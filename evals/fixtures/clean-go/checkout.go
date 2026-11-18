package checkout

import (
	"errors"

	"example.com/clean/internal/sdk"
)

var ErrEmpty = errors.New("empty cart")

func Pay(payments []sdk.Payment) (sdk.Payment, error) {
	if len(payments) == 0 {
		return sdk.Payment{}, ErrEmpty
	}
	total := sdk.Total(payments)
	return sdk.CreatePayment(total, "usd"), nil
}
