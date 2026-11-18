pub struct Payment {
    pub amount: u32,
}

pub fn create_payment(amount: u32) -> Payment {
    Payment { amount }
}

fn internal_helper() {}

pub fn describe(payment: &Payment) -> String {
    format!("{}", payment.amount)
}
