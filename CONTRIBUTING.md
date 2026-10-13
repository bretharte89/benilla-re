# Contributing

Corrections, names, findings and tests are all welcome. Read `METHOD.md` first: it says what
counts as evidence here. The formats are in `symbols/README.md` and `systems/README.md`.

## Setup

Bring your own client. Nothing from the game is in this repo, and nothing from it may be added:
no exe, no MPQ, no extracted file, no disassembly or decompiler dump.

1. Copy your `WoW.exe` from a 1.12.1 (build 5875) install to `WoW/WoW.exe` at the repo root,
   and its `Data` folder to `WoW/Data`. `WoW/` is ignored by git.
2. Check it is the same build the findings were read from:

   | | |
   |---|---|
   | SHA-256 | `b4756d38ef207c02ed651f4952bd89a70b4857b73a33413339e1b285b28d2dc7` |
   | size | 4,775,986 bytes |

   `shasum -a 256 WoW/WoW.exe` on macOS and Linux, `certutil -hashfile WoW\WoW.exe SHA256` on
   Windows. A different hash is a different build, and the addresses here do not apply to it.
3. Read the code. Any disassembler works. The exe is a 32-bit PE with image base 0x400000, so
   the addresses in this repo are the addresses your tool shows. With LLVM's objdump:

   ```
   objdump -d -M intel --start-address=0x514ae0 --stop-address=0x514b35 WoW/WoW.exe
   ```

A setup script will import the exe into Ghidra with recorded options, create the functions its
analysis misses, apply the symbol table, and write the full disassembly to the ignored `dumps/`.
A single check will verify the table, the docs and the tests together, refusing any other build
of the exe. Neither exists yet. Until they do, `tools/validate.py` checks the table and the docs
against their formats, and review does the rest by hand.

## Adding a name

1. Find the function's row in `symbols/functions.tsv`, or add one in address order.
2. Read the function at the bytes, enough to state its meaning in one line, and record the
   derivation in its system's doc: a new entry, or a line in the entry that covers the mechanism.
3. Fill `name`, `meaning`, `confidence`, `proof` and `finding`. A name you give follows the
   client's C++ style (`symbols/README.md`): `Class::Method` where the class is established,
   otherwise a PascalCase name that says what the function does, not where you met it.
4. A name from `vmangos/idb` is checked at the bytes before use, keeps its spelling, and gets
   `idb` in `name_from`. A community name that the bytes contradict is not used.

One row per address. If the address already has a row in another system, the owner stays; your
finding can live in your system's doc and the row can link there.

## Adding a finding

1. Pick the system doc, or start one from the shape in `systems/README.md`.
2. Write the entry: the claim, the addresses that decide it, the confidence, the proof, the test,
   and the derivation from the bytes.
3. Give every address the entry cites a row, and point each row's `finding` at the entry.
4. If the claim is one that spreads (the wire, the disk, shared maths, the frame and event core,
   a system's roots), it needs a second independent reading before its proof is `two`. Ask for
   one in the pull request; the second reader works from the addresses and the question alone.
5. If the finding contradicts an existing entry, find the instruction one of them misread, and
   rewrite the wrong entry. Say what was wrong and where in the commit message.

## Adding a test

Tests live in `crates/<crate>/tests/` and run the exe's own code in the Unicorn emulator beside a
Rust reimplementation, comparing the results bit for bit.

- Test the whole function where possible; a slice test names the instructions it covers.
- Cover every regime the code distinguishes, with a deterministic probe at each threshold.
- When the test passes against the exe, set the row's `test` to `crate::test_fn` and its `proof`
  to `test`.
- A test that cannot find the exe reports itself skipped. A skip is not a pass.

The emulator is `unicorn-engine` (GPL-2.0), used as a test dependency only; nothing that ships
links it.

## Review

Every change lands by pull request, and a reviewer checks:

- that `tools/validate.py` passes: every cited address resolves to a row, every row's `finding`
  resolves to an entry that mentions its address, and the text limits hold;
- each new or changed claim against the bytes, by reading the cited instructions;
- that `verified` rows have a derivation, `inferred` rows say `none` for proof, and `two` is
  claimed only with a second reader who worked cold;
- that a correction rewrites the wrong entry instead of adding a second one beside it.

Keep a pull request to one system or one mechanism. Quote a few instructions where they decide a
point; never paste a listing.

## License

MIT OR Apache-2.0, at your option. By contributing you agree that your contribution is licensed
the same way.
