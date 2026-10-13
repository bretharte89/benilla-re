//! `cargo xtask`: the repo's own tooling.

mod bodies;
mod check;
mod cited;
mod exe;
mod tables;
mod tree;

use std::path::{Path, PathBuf};
use std::process::ExitCode;

const USAGE: &str = "\
usage: cargo xtask check [--exe]
       cargo xtask cited <benilla checkout>

check         the symbol table and the system docs against their formats; runs anywhere
check --exe   also identifies WoW/WoW.exe (or $BENILLA_RE_WOW_EXE), checks every function
              row's body against dumps/disasm.txt (written when missing), regenerates the
              tables, runs every test with BENILLA_RE_REQUIRE_EXE=1, and requires each test
              the table and the docs name to pass
cited         lists the client addresses a benilla tree cites that no row or doc here backs
";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    let root = root();
    let result = match args.as_slice() {
        ["check"] => check(&root, false),
        ["check", "--exe"] => check(&root, true),
        ["cited", benilla] => cited(&root, Path::new(benilla)),
        _ => {
            eprint!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    match result {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("xtask: {error}");
            ExitCode::from(2)
        }
    }
}

/// The repo root: the directory that holds `xtask/`.
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("xtask sits in the repo root")
        .to_path_buf()
}

/// Prints one line per problem and a summary; true when there is none.
fn check(root: &Path, with_exe: bool) -> std::io::Result<bool> {
    let checked = check::run(&tree::Disk::new(root))?;
    let mut problems = checked.problems.clone();
    let mut summary = checked.summary();
    if with_exe {
        let outcome = exe::run(root, &checked)?;
        problems.extend(outcome.problems);
        summary = format!("{summary}; {}", outcome.summary);
    }
    for problem in &problems {
        println!("{problem}");
    }
    println!("{summary}: {} problems", problems.len());
    Ok(problems.is_empty())
}

fn cited(root: &Path, benilla: &Path) -> std::io::Result<bool> {
    let checked = check::run(&tree::Disk::new(root))?;
    cited::run(&checked, benilla)?;
    Ok(true)
}
