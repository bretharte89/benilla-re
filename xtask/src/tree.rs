//! The files a check reads, addressed by `/`-separated paths relative to the repo root.

use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub trait Tree {
    /// The text of the file at `path`: `None` when there is no such file, an `InvalidData` error
    /// when it is not UTF-8.
    fn read(&self, path: &str) -> io::Result<Option<String>>;

    /// Every file in the tree, sorted.
    fn files(&self) -> io::Result<Vec<String>>;
}

/// The repo on disk.
pub struct Disk {
    root: PathBuf,
}

/// Directories the repo's walk does not enter: build output, the reader's own client,
/// regenerated dumps, and the check's fixtures, whose planted violations are test data rather
/// than the repo's claims.
const SKIPPED: [&str; 4] = ["target", "WoW", "dumps", "xtask/fixtures"];

impl Disk {
    pub fn new(root: &Path) -> Disk {
        Disk {
            root: root.to_path_buf(),
        }
    }
}

/// Every file under `root`, by its path relative to `root`, sorted. Not entered: hidden
/// directories, the `skipped` paths, and build caches (a directory holding `CACHEDIR.TAG`, as
/// cargo's `target` does). Symbolic links are not followed.
pub fn files(root: &Path, skipped: &[&str]) -> io::Result<Vec<String>> {
    let mut found = Vec::new();
    walk(root, "", skipped, &mut found)?;
    found.sort();
    Ok(found)
}

fn walk(dir: &Path, prefix: &str, skipped: &[&str], found: &mut Vec<String>) -> io::Result<()> {
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        if name.starts_with('.') {
            continue;
        }
        let path = format!("{prefix}{name}");
        let kind = entry.file_type()?;
        if kind.is_dir() {
            if !skipped.contains(&path.as_str()) && !entry.path().join("CACHEDIR.TAG").exists() {
                walk(&entry.path(), &format!("{path}/"), skipped, found)?;
            }
        } else if kind.is_file() {
            found.push(path);
        }
    }
    Ok(())
}

impl Tree for Disk {
    fn read(&self, path: &str) -> io::Result<Option<String>> {
        match fs::read(self.root.join(path)) {
            Ok(bytes) => String::from_utf8(bytes).map(Some).map_err(|_| {
                io::Error::new(io::ErrorKind::InvalidData, format!("{path} is not UTF-8"))
            }),
            Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(error),
        }
    }

    fn files(&self) -> io::Result<Vec<String>> {
        files(&self.root, &SKIPPED)
    }
}

/// A tree held in memory, for tests that plant a violation in a copy of a fixture.
#[cfg(test)]
pub struct Memory(pub std::collections::BTreeMap<String, String>);

#[cfg(test)]
impl Tree for Memory {
    fn read(&self, path: &str) -> io::Result<Option<String>> {
        Ok(self.0.get(path).cloned())
    }

    fn files(&self) -> io::Result<Vec<String>> {
        Ok(self.0.keys().cloned().collect())
    }
}

/// Every file under `root` with its text.
#[cfg(test)]
pub fn load(root: &Path) -> std::collections::BTreeMap<String, String> {
    let disk = Disk::new(root);
    disk.files()
        .expect("the fixture is readable")
        .into_iter()
        .map(|path| {
            let text = disk.read(&path).expect("readable").expect("present");
            (path, text)
        })
        .collect()
}
