mod sdk;

use crate::sdk::{Payment, create_charge, internal_helper};
use rand::Rng;
use crate::missing::Thing;

fn main() {
    let _payment: Payment = create_charge(10);
    internal_helper();
    let _n: u32 = rand::thread_rng().gen();
    let _t: Option<Thing> = None;
}
