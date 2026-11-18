fn parse(raw: &str) -> u32 {
    raw.parse().unwrap()
}

fn run(items: &[u32]) {
    for item in items {
        match item {
            0 => {}
            _ => {}
        }
    }
    let _ = std::fs::read_to_string("config.toml");
    println!("done");
}

fn lookup(map: &std::collections::HashMap<String, u32>, key: &str) -> u32 {
    *map.get(key).expect("")
}

fn placeholder() -> u32 {
    todo!()
}

fn unchecked(value: i64) -> u32 {
    value as u32
}

fn lookup_again(map: &std::collections::HashMap<String, u32>, key: &str) -> u32 {
    *map.get(key).expect("failed")
}
