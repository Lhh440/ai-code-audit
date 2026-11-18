mod money;

use crate::money::{Cents, total};

fn main() {
    let items = vec![Cents(100), Cents(250)];
    match total(&items) {
        Ok(sum) => println!("{sum}"),
        Err(error) => eprintln!("{error}"),
    }
}
