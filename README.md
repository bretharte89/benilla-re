# benilla-re

The reverse engineering of the World of Warcraft 1.12.1 client (`WoW.exe`, build 5875) behind
[benilla](https://github.com/samwhosung/benilla), a from-scratch 1.12.1 client in Rust.

What the client does, read at its bytes and cited by address: the functions, globals and
structures it is made of, what each one does, and Rust reference implementations whose tests run
the client's own machine code beside ours and compare the results bit for bit.

Bring your own client. Nothing here comes from a WoW install: the tests and tools read
`WoW/WoW.exe` and `WoW/Data` from your own copy of 1.12.1.5875, and skip without it.

## License

MIT OR Apache-2.0, at your option.
