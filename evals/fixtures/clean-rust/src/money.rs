use std::fmt;

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Cents(pub u32);

impl fmt::Display for Cents {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{:02}", self.0 / 100, self.0 % 100)
    }
}

#[derive(Debug)]
pub struct EmptyCart;

impl fmt::Display for EmptyCart {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "empty cart")
    }
}

pub fn total(items: &[Cents]) -> Result<Cents, EmptyCart> {
    if items.is_empty() {
        return Err(EmptyCart);
    }
    let sum = items.iter().map(|item| item.0).sum();
    Ok(Cents(sum))
}
