//! Every function row against the disassembly `tools/disasm.sh` writes: that the row's address
//! starts a function (`METHOD.md`, Completeness) and that its size is its body's, by the rule in
//! `symbols/README.md`. The exe supplies the jump tables.

use crate::check::Problem;
use regex::Regex;
use std::collections::HashSet;
use std::fs::File;
use std::io::{self, BufRead, BufReader};
use std::path::Path;
use std::sync::LazyLock;

macro_rules! pattern {
    ($name:ident, $source:expr) => {
        static $name: LazyLock<Regex> =
            LazyLock::new(|| Regex::new($source).expect("a valid pattern"));
    };
}

pattern!(DIRECT, r"^(j[a-z]+|loop[a-z]*)\s+0x([0-9a-f]+)$");
pattern!(TABLE, r"^jmp\s+DWORD PTR \[e[a-z]{2}\*4\+0x([0-9a-f]+)\]$");
pattern!(
    TABLE_READ,
    r"(?:DWORD PTR \[e[a-z]{2}\*4|BYTE PTR \[e[a-z]{2})\+0x([0-9a-f]+)\]"
);

/// A switch's tables sit at the end of its function: code this close after one is data's
/// neighbour, not fall-through.
const TABLE_REACH: u32 = 0x400;

/// The listing: each instruction's address and its text, whitespace runs collapsed.
pub struct Listing {
    addresses: Vec<u32>,
    ends: Vec<usize>,
    text: String,
}

impl Listing {
    pub fn read(path: &Path) -> io::Result<Listing> {
        Listing::parse(BufReader::new(File::open(path)?))
    }

    pub fn parse(reader: impl BufRead) -> io::Result<Listing> {
        let mut pairs: Vec<(u32, String)> = Vec::new();
        for line in reader.split(b'\n') {
            let line = line?;
            let line = String::from_utf8_lossy(&line);
            let line = line.trim_start();
            let Some((address, rest)) = line.split_once(':') else {
                continue;
            };
            let Some(rest) = rest.strip_prefix('\t') else {
                continue;
            };
            if address.is_empty()
                || !address
                    .bytes()
                    .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
            {
                continue;
            }
            let Ok(address) = u32::from_str_radix(address, 16) else {
                continue;
            };
            let words: Vec<&str> = rest.split_whitespace().collect();
            pairs.push((address, words.join(" ")));
        }
        // A repeated address keeps its last text.
        pairs.reverse();
        pairs.sort_by_key(|p| p.0);
        pairs.dedup_by_key(|p| p.0);
        let mut listing = Listing {
            addresses: Vec::with_capacity(pairs.len()),
            ends: Vec::with_capacity(pairs.len()),
            text: String::new(),
        };
        for (address, text) in pairs {
            listing.text.push_str(&text);
            listing.addresses.push(address);
            listing.ends.push(listing.text.len());
        }
        Ok(listing)
    }

    pub fn len(&self) -> usize {
        self.addresses.len()
    }

    fn index(&self, address: u32) -> Option<usize> {
        self.addresses.binary_search(&address).ok()
    }

    fn at(&self, index: usize) -> &str {
        let start = if index == 0 { 0 } else { self.ends[index - 1] };
        &self.text[start..self.ends[index]]
    }

    fn get(&self, address: u32) -> Option<&str> {
        self.index(address).map(|i| self.at(i))
    }

    /// The first instruction after `address`.
    fn following(&self, address: u32) -> Option<u32> {
        let i = self.addresses.partition_point(|&a| a <= address);
        self.addresses.get(i).copied()
    }

    /// The last instruction before `address`.
    fn preceding(&self, address: u32) -> Option<u32> {
        let i = self.addresses.partition_point(|&a| a < address);
        i.checked_sub(1).map(|i| self.addresses[i])
    }
}

/// The exe's sections as file bytes, for reading jump tables.
pub struct Image<'a> {
    bytes: &'a [u8],
    /// Each section's virtual address, raw size and file offset.
    sections: Vec<(u32, u32, u32)>,
}

impl<'a> Image<'a> {
    pub fn new(bytes: &'a [u8]) -> Option<Image<'a>> {
        let u16_at = |o: usize| Some(u16::from_le_bytes(bytes.get(o..o + 2)?.try_into().ok()?));
        let u32_at = |o: usize| Some(u32::from_le_bytes(bytes.get(o..o + 4)?.try_into().ok()?));
        let pe = u32_at(0x3c)? as usize;
        let count = u16_at(pe + 6)? as usize;
        let optional = u16_at(pe + 20)? as usize;
        let base = u32_at(pe + 52)?;
        let table = pe + 24 + optional;
        let mut sections = Vec::new();
        for i in 0..count {
            let header = table + 40 * i;
            let address = u32_at(header + 12)?;
            let raw_size = u32_at(header + 16)?;
            let raw_offset = u32_at(header + 20)?;
            sections.push((base.wrapping_add(address), raw_size, raw_offset));
        }
        Some(Image { bytes, sections })
    }

    fn dword(&self, address: u32) -> Option<u32> {
        let address = u64::from(address);
        for &(start, size, offset) in &self.sections {
            let (start, size) = (u64::from(start), u64::from(size));
            if start <= address && address + 4 <= start + size {
                let at = (u64::from(offset) + address - start) as usize;
                return Some(u32::from_le_bytes(
                    self.bytes.get(at..at + 4)?.try_into().ok()?,
                ));
            }
        }
        None
    }
}

fn is_padding(instruction: &str) -> bool {
    instruction == "nop" || instruction == "int3"
}

struct Context<'a> {
    listing: &'a Listing,
    image: &'a Image<'a>,
    starts: HashSet<u32>,
    jcc_targets: HashSet<u32>,
    /// Jump and index tables inside the listing's range, sorted.
    data: Vec<u32>,
}

impl Context<'_> {
    fn after_table(&self, address: u32, entry: u32) -> bool {
        let i = self.data.partition_point(|&d| d <= address);
        i > 0 && entry.wrapping_sub(self.data[i - 1]) < TABLE_REACH
    }

    /// The instructions reached from `entry`, and the jump tables they index.
    fn body(&self, entry: u32) -> (HashSet<u32>, Vec<(u32, u32)>) {
        let (mut reached, mut tables, mut work) = (HashSet::new(), Vec::new(), vec![entry]);
        while let Some(start) = work.pop() {
            let mut address = Some(start);
            while let Some(here) = address {
                let Some(instruction) = self.listing.get(here) else {
                    break;
                };
                if !reached.insert(here) {
                    break;
                }
                if instruction.starts_with("ret") || instruction.starts_with("int3") {
                    break;
                }
                if let Some(found) = DIRECT.captures(instruction) {
                    let Ok(target) = u32::from_str_radix(&found[2], 16) else {
                        break;
                    };
                    if &found[1] == "jmp" {
                        if self.starts.contains(&target) && target != entry {
                            break;
                        }
                        address = Some(target);
                        continue;
                    }
                    work.push(target);
                } else if let Some(found) = TABLE.captures(instruction) {
                    let table = u32::from_str_radix(&found[1], 16).unwrap_or(0);
                    let mut k = 0;
                    while let Some(value) = self.image.dword(table.wrapping_add(4 * k)) {
                        if !(entry <= value && value < table) || self.listing.get(value).is_none() {
                            break;
                        }
                        work.push(value);
                        k += 1;
                    }
                    tables.push((table, table.wrapping_add(4 * k)));
                    break;
                } else if instruction.starts_with("jmp") {
                    break;
                }
                address = self.listing.following(here);
            }
        }
        (reached, tables)
    }
}

/// A function row: its place in the table, its address and its size.
pub struct Function {
    pub place: String,
    pub address: u32,
    pub size: u32,
}

/// Checks every row; returns the problems.
pub fn check(rows: &[Function], listing: &Listing, image: &Image) -> Vec<Problem> {
    let (Some(&first), Some(&last)) = (listing.addresses.first(), listing.addresses.last()) else {
        return vec![Problem {
            place: "dumps/disasm.txt".to_string(),
            message: "holds no instruction".to_string(),
        }];
    };
    let mut jcc_targets = HashSet::new();
    let mut data = HashSet::new();
    for i in 0..listing.len() {
        let instruction = listing.at(i);
        if instruction.starts_with('j') || instruction.starts_with("loop") {
            if let Some(found) = DIRECT.captures(instruction) {
                if &found[1] != "jmp" {
                    if let Ok(target) = u32::from_str_radix(&found[2], 16) {
                        jcc_targets.insert(target);
                    }
                }
            }
        }
        if instruction.contains("PTR [e") {
            for found in TABLE_READ.captures_iter(instruction) {
                if let Ok(table) = u32::from_str_radix(&found[1], 16) {
                    if first <= table && table <= last {
                        data.insert(table);
                    }
                }
            }
        }
    }
    let mut data: Vec<u32> = data.into_iter().collect();
    data.sort_unstable();
    let context = Context {
        listing,
        image,
        starts: rows.iter().map(|r| r.address).collect(),
        jcc_targets,
        data,
    };

    let mut problems = Vec::new();
    let mut add = |row: &Function, message: String| {
        problems.push(Problem {
            place: row.place.clone(),
            message,
        })
    };
    for row in rows {
        let (entry, size) = (row.address, row.size);
        if listing.get(entry).is_none() {
            add(row, "not an instruction start in the listing".to_string());
            continue;
        }
        let mut before = listing.preceding(entry);
        while let Some(b) = before.filter(|&b| is_padding(listing.get(b).unwrap_or_default())) {
            before = listing.preceding(b);
        }
        if let Some(b) = before {
            let instruction = listing.get(b).unwrap_or_default();
            let ends = ["ret", "jmp", "int3"]
                .iter()
                .any(|e| instruction.starts_with(e));
            if !ends && !context.after_table(b, entry) {
                add(
                    row,
                    format!("reached by fall-through from {b:#x}, so code of the function above"),
                );
            }
        }
        if context.jcc_targets.contains(&entry) {
            add(row, "a conditional jump lands on it".to_string());
        }
        let (reached, tables) = context.body(entry);
        let last_reached = reached.iter().copied().max().unwrap_or(entry);
        match listing.following(last_reached) {
            Some(end) if end - entry != size => {
                add(row, format!("size {size}, body {}", end - entry));
            }
            Some(_) => {}
            None => add(row, "the body runs to the end of the listing".to_string()),
        }
        let low = listing.addresses.partition_point(|&a| a < entry);
        let high = listing
            .addresses
            .partition_point(|&a| u64::from(a) < u64::from(entry) + u64::from(size));
        for i in low..high {
            let address = listing.addresses[i];
            if reached.contains(&address) || is_padding(listing.at(i)) {
                continue;
            }
            if tables.iter().any(|&(s, e)| s <= address && address < e) {
                continue;
            }
            add(
                row,
                format!("{address:#x} lies inside the extent but outside the body"),
            );
            break;
        }
    }
    problems
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Three functions: one with a conditional branch and a call, a switch through a jump table
    /// whose data follows its code, and a tail jump after the table.
    const LISTING: &str = "
WoW.exe:     file format pei-i386

00401000 <.text>:
  401000:\tpush   ebp
  401001:\tmov    ebp,esp
  401003:\tje     0x40100a
  401005:\tcall   0x401040
  40100a:\tpop    ebp
  40100b:\tret
  40100c:\tnop
  40100d:\tnop
  40100e:\tint3
  40100f:\tnop
  401010:\tmov    eax,ecx
  401012:\tjmp    DWORD PTR [eax*4+0x401030]
  401019:\tmov    eax,0x1
  40101e:\tret
  40101f:\tmov    eax,0x2
  401024:\tret
  401025:\tnop
  401030:\tsbb    BYTE PTR [eax+0x40],dl
  401034:\tsbb    BYTE PTR [eax+0x40],bl
  401038:\tadd    BYTE PTR [eax],al
  40103a:\tadd    BYTE PTR [eax],al
  401040:\tjmp    0x401010
  401045:\tnop
";

    /// A PE with one section at 0x401000 whose file bytes hold the jump table at 0x401030.
    fn image_bytes() -> Vec<u8> {
        let mut bytes = vec![0u8; 0x400];
        let put = |bytes: &mut Vec<u8>, at: usize, value: u32| {
            bytes[at..at + 4].copy_from_slice(&value.to_le_bytes());
        };
        put(&mut bytes, 0x3c, 0x40);
        bytes[0x46] = 1; // one section
        bytes[0x54] = 0xe0; // the optional header's size
        put(&mut bytes, 0x40 + 52, 0x400000);
        let section = 0x40 + 24 + 0xe0;
        put(&mut bytes, section + 12, 0x1000);
        put(&mut bytes, section + 16, 0x200);
        put(&mut bytes, section + 20, 0x200);
        put(&mut bytes, 0x230, 0x401019);
        put(&mut bytes, 0x234, 0x40101f);
        bytes
    }

    fn problems(rows: &[(u32, u32)]) -> Vec<String> {
        let listing = Listing::parse(LISTING.as_bytes()).expect("parses");
        let bytes = image_bytes();
        let image = Image::new(&bytes).expect("a PE");
        let rows: Vec<Function> = rows
            .iter()
            .map(|&(address, size)| Function {
                place: format!("{address:#x}"),
                address,
                size,
            })
            .collect();
        check(&rows, &listing, &image)
            .iter()
            .map(|p| p.to_string())
            .collect()
    }

    const CLEAN: [(u32, u32); 3] = [(0x401000, 12), (0x401010, 21), (0x401040, 5)];

    #[test]
    fn bodies_follow_branches_tables_and_tail_jumps() {
        assert_eq!(problems(&CLEAN), Vec::<String>::new());
    }

    #[test]
    fn each_misfit_is_named() {
        let with = |extra: (u32, u32)| {
            let mut rows = CLEAN.to_vec();
            rows.push(extra);
            rows.sort();
            problems(&rows)
        };
        let mut wrong_size = CLEAN;
        wrong_size[0].1 = 10;
        assert_eq!(problems(&wrong_size), ["0x401000: size 10, body 12"]);
        assert_eq!(
            with((0x401002, 1)),
            ["0x401002: not an instruction start in the listing"]
        );
        assert_eq!(
            with((0x401005, 7)),
            ["0x401005: reached by fall-through from 0x401003, so code of the function above"]
        );
        assert_eq!(
            with((0x40100a, 2)),
            [
                "0x40100a: reached by fall-through from 0x401005, so code of the function above",
                "0x40100a: a conditional jump lands on it",
            ]
        );
        let mut long = CLEAN;
        long[1].1 = 0x30;
        assert_eq!(
            problems(&long),
            [
                "0x401010: size 48, body 21",
                "0x401010: 0x401038 lies inside the extent but outside the body",
            ]
        );
    }
}
