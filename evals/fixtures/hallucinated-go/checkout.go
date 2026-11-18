package checkout

import (
	"example.com/fixture/internal/sdk"
	"github.com/google/uuid"
)

func Pay(total int) sdk.Payment {
	return sdk.CreateCharge(total, "usd")
}

func PayWithHelper(total int) sdk.Payment {
	return sdk.helper()
}

func PayWithID(total int) (sdk.Payment, error) {
	id, err := uuid.NewV7()
	if err != nil {
		return sdk.Payment{}, err
	}
	_ = id
	return sdk.CreatePayment(total, "usd"), nil
}
