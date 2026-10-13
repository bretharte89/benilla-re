# glue: survey and patch downloads

The two files the logon server can push before the realm list: a patch and a survey.

When the logon server offers a file transfer, the per-frame update (`flow`) starts a patch
download for a transfer named `Patch` and a survey download for `Survey`. Both write through
net's download file (`net` rows `0x5b03f0` to `0x5b0ce0`): `SurveyDownloadGlue.cpp` keeps its
file at `0xb421c0`, `PatchDownloadGlue.cpp` at `0xb42260`, and the session's file-data callback
hands each chunk to whichever is open. A finished patch is applied from the script and quits the
client; a finished survey is unpacked from its archive, run as a DLL, and its packed result sent
back to the logon server before the login goes on. Screen state 10 is a download in progress and
11 a survey to run (`0xb41da0`, `flow`).

Roots: `0x474610`, `0x473c30`, `0x474b50`, `0x473d50`, `0x474b70`, `0x473d70`, `0x473ce0`, `0x473f10`, `0x473df0`, `0x473e30`, `0x474710`, `0x4749f0`

## Patch download

`0x474610` closes the status dialog (glue event 5), sets screen state 10, shows the
`patchdownload` screen, replaces any open patch file, opens a new one under the transfer's name,
or `wow-patch.mpq` for `Patch`, and accepts the transfer at the offset the open returns. Each
chunk is written to the file. While in state 10 the update polls it. Complete raises
`PATCH_DOWNLOADED` (17) with progress 1.0 and finishes the file, then polls again: failed now
shows the failure dialog, else state 0; the file is freed either way. Failed shows the failure
dialog. Otherwise, at most every 250 ms, it stores the progress, raises `PATCH_UPDATE_PROGRESS`
(16), and cancels with `DISCONNECTED` when the logon link is down.

Addresses: `0x474610`, `0x47461e`, `0x474628`, `0x4746c3`, `0x4746e9`, `0x4746f8`, `0x474b50`, `0x46b910`, `0x474b70`, `0x474b8a`, `0x474bc7`, `0x474bcf`, `0x474c37`, `0x474c5e`, `0x474c76`, `0x474c8b`, `0xb42260`, `0xb414c0`, `0xb41d7c`
Confidence: verified
Proof: one
Test: none

`0x47461e` is `SignalEvent` with `ecx` 5; `0x474628` stores 10 in `0xb41da0` before
`SetScreen("patchdownload")`. The name is the session's `+0x98`, compared case-insensitively with
`Patch` at `0x4746c3`; the open at `0x4746e9` takes the digest `+0x88` and the size `+0x80`,
`+0x84`; `0x4746f8` passes its result and offset to `AnswerLoginFileTransfer 0x5ab5d0`.
`0x46b910`, called by the session's data callback, jumps to `0x474b50` when `0xb42260` is set,
else to the survey's feed. In `0x474b70`, state 2 stores 1.0 (`0x474b8a`), signals 17, calls
`DownloadFileFinish 0x5b0ab0`, and `0x474bc7` to `0x474bcf` send a state of 3 to the failure call at
`0x474c37`; state 3 takes the same path; otherwise `0x474c5e` requires `now − 0xb41d7c > 250` (unsigned), and
`0x474c76` stores `DownloadFileProgress`'s float in `0xb414c0`, the value `PatchDownloadProgress`
returns. Only inside that 250 ms branch, a cleared session byte `+0x5` (`0x474c8b`) cancels and shows
`DISCONNECTED` with `OKAY`.

## Patch failure dialog

A failed download or apply logs off the logon server, returns to the `login` screen in state 0,
and raises `OPEN_STATUS_DIALOG` with `OKAY` and a text: for failure code 2,
`PATCH_FAILED_DISK_FULL` formatted with the second value raised to at least 2; for any other
code, `PATCH_FAILED_MESSAGE`. A failed download passes the file's error code and a second value
from the file; a failed apply passes code 4, 5 or 6 with 0, so it always shows the message.

Addresses: `0x474ab0`, `0x474ac6`, `0x474ae4`, `0x474af7`, `0x474b1e`, `0x474b39`, `0x474c48`
Confidence: verified
Proof: one
Test: none

`0x474ab0` takes the code in `ecx` and the value in `edx`. `0x474ac6` calls `CancelLogon
0x5b3320`, then state 0 and `SetScreen("login")`. `0x474ae4` branches on code 2; `0x474af7` `cmp
esi,2; jae` keeps a value of 2 or more, else stores 2; `0x474b1e` formats it into the looked-up
text with `%d`-style `SStrPrintf` into a 1,024-byte buffer. `0x474b39` is `SignalEvent2(3, "%s%s",
"OKAY", text)`. The download's call at `0x474c48` passes the file's `+0x13c` and `+0x148`.

## Patch cancel

Cancelling a patch download aborts and frees the file, cancels the transfer, returns to state
0, logs off the logon server and shows the `login` screen. `PatchDownloadCancel` and a lost
logon connection during the download both take this path.

Addresses: `0x474710`, `0x474717`, `0x47474f`, `0x474754`, `0x474765`, `0x474770`
Confidence: verified
Proof: one
Test: none

`0x474717` calls `DownloadFileAbort 0x5b0b20`, then the file is closed, freed and `0xb42260`
cleared; `0x47474f` is `CancelFileTransfer 0x5b20d0` with 0; `0x474754` stores state 0;
`0x474765` is `CancelLogon`; `0x474770` tail-jumps to `SetScreen("login")`. Its callers are the
binding `0x46d400` and the disconnect check at `0x474c92`.

## Applying the patch

`PatchDownloadApply` opens `wow-patch.mpq` as an archive, checks its signature, runs the
archive's `prepatch.lst`, closes it, and on success quits the client with code 0, deleting the
patch first when the list asked for it. Failure deletes `wow-patch.mpq` and shows the failure
dialog: code 4 when the open failed with error 2, 5 for any other open failure or a signature
result from 1 to 4, and 6 when a list command failed.

Addresses: `0x4749f0`, `0x474a09`, `0x474a1b`, `0x474a52`, `0x474a5e`, `0x474a6d`, `0x474a91`, `0x474aa4`, `0x46b870`, `0xb42264`
Confidence: verified
Proof: one
Test: none

`0x474a09` opens the archive with priority 100; `0x474a1b` reads the open's error, and `sub
eax,2; je` picks 4, else 5. `0x474a52` writes a signature result to `[ebp-0x8]`; `0x474a5e`: a
nonzero result below 5 is a failure, while 0 and 5 or more go on to the list (`0x474a6d`), whose
zero return gives 6. Every failure reaches `0x474a2a`: `0x474ab0(code, 0)`, then the file is
deleted. Success tests `0xb42264` (`0x474a91`), deletes the patch when it is set, and calls
`0x46b870`, which is `xor ecx,ecx; jmp 0x401560`: quit with exit code 0. What the signature
results mean is the archive code's, not read here.

## The prepatch list

`prepatch.lst` is read from the archive and split into lines at `\r\n`. Each line is a
command: `extract <file>` writes the archive's file of that name to disk; `execute <file>` starts
it as a process with an empty command line; `delete <path>` deletes the file, or, when no file
of that name exists, removes the directory of that name. `delete wow-patch.mpq` only marks the
patch for deletion after the list. Lines run in order; other lines are ignored. The list fails,
and stops, at the first extract or launch that fails; a list that cannot be loaded fails too.

Addresses: `0x474890`, `0x4748bc`, `0x4748f8`, `0x474914`, `0x474930`, `0x474968`, `0x4749a0`, `0x4749a5`, `0x474790`, `0x4747ce`, `0x474820`, `0x474830`, `0x474847`, `0x474855`, `0x47485e`, `0x474877`
Confidence: verified
Proof: one
Test: none

`0x4748f8` tokenizes at the separator into a 260-byte buffer; `0x474914`, `0x47494e` and
`0x474986` compare the token's first 8, 8 and 7 bytes with `extract `, `execute ` and `delete `,
and hand the rest of the token to `0x474790`, `0x474820` or `0x474830`, whose return becomes the
running result (`0x4749a5`); an unmatched token leaves it. The loop at `0x4748d0` stops on an end
of text or a zero result. `0x474790` loads the file from the archive and creates the output
(`0x4747ce`: write access, create always); it returns 0 when the load or the create fails.
`0x474820` returns what the launcher returns. `0x474830` always returns 1: `0x42a4e0` true means
a file exists, then `0x474847` compares the name with `wow-patch.mpq` and `0x474855` sets
`0xb42264`, or `0x47485e` deletes it; otherwise `0x474877` removes the directory when `0x42a500`
reports one.

## Survey download

A survey transfer sets screen state 10 and opens `WDB\Survey.mpq` as a download in the same way
as a patch, with its own file. While it downloads, the update polls it: complete finishes the
file and moves to state 11, failed deletes it and moves to state 11 too. Cancelling the status
dialog during the download aborts and frees it, cancels the transfer, returns to state 0 and
logs off the logon server.

Addresses: `0x473c30`, `0x473c40`, `0x473cbe`, `0x473ccd`, `0x473d50`, `0x473d70`, `0x473da8`, `0x473dde`, `0x473de3`, `0x473ce0`, `0x473d36`, `0xb421c0`
Confidence: verified
Proof: one
Test: none

`0x473c40` stores 10 before replacing the file at `0xb421c0`; `0x473cbe` opens `WDB\Survey.mpq`
with the session's digest and size and `0x473ccd` answers the transfer. `0x473d50` feeds a
chunk when the file exists. `0x473d70`: state 2 cancels the transfer with 1 when the file's
`+0x140` byte is set, finishes the file and stores 11 (`0x473da8`); state 3 cancels with 0 when
it is set, closes the file with deletion (`0x473dde`) and stores 11 (`0x473de3`). `0x473ce0`,
called from the status-dialog click, aborts, closes and frees the file, cancels the transfer,
stores state 0 and tail-jumps to `CancelLogon` (`0x473d36`).

## Running the survey

In state 11, with a complete survey file, the update runs the survey once: the archive's
signature must give a result of at least 5; `Survey.dll` is extracted to `WDB\Survey.dll`,
loaded, and its `ExtraWork` export called with a zeroed 4,100-byte block holding 4, 8, the
locale code and the survey id. A nonzero return with a length of at most 4,096 is compressed with
zlib at level 9 into 8,192 bytes, and a compressed result of at most 1,000 bytes is kept. Without a kept result the client
sends a survey failure. The DLL is unloaded and deleted, and the archive closed.

Addresses: `0x473f10`, `0x473f40`, `0x473f66`, `0x473f6b`, `0x473f8c`, `0x473fd3`, `0x473ff4`, `0x474015`, `0x47404f`, `0x47406e`, `0x474079`, `0x4740b8`, `0x4740c4`, `0x47413b`, `0x47416b`, `0x474780`, `0xb421f0`, `0xb421f4`
Confidence: verified
Proof: one
Test: none

`0x473f66` checks the archive with the 256-byte key at `0x838848` and the exponent bytes
`01 00 01 00`; `0x473f6b` `cmp [ebp-0x24],5; jb` fails below 5. The file write must write the
whole size (`0x473fd3`, `0x473fdb`). `0x474780`, called at `0x473ff4`, is a lone `ret`.
`0x47404f` stores the words 4 and 8 at `+0x0` and `+0x2`, then the locale dword and
`GetSurveyId 0x5ab620`; `0x47406e` calls the export with the block in `ecx`. `0x474079` requires
the word at `+0x2` to be at most `0x1000`; `0x4740b8` compresses `+0x4` through `0x730bc0` (a
0x38-byte stream, version `1.2.2`, flush 4, −5 when the output is too small) with level 9, and `0x4740c4`
keeps a size of at most `0x3e8` in `0xb421f4` with a copy at `0xb421f0`. `0x47413b` is
`SendSurveyFailure 0x5ab610`. `0x47416b` deletes the DLL when it exists.

## Survey result and return

A successful run opens a `CANCEL` status dialog with `LOGIN_STATE_SURVEY`, sends the kept
result, and stamps the time; 1.5 s later the update ends the survey. Ending it frees the result
and the file and tells the logon listener that the login is authenticated, which returns the
glue to state 1. A failed run, or a survey file that is missing or incomplete in state 11, ends
it at once. `SurveyNotificationDone` sends the result when its first argument reads as true,
and then ends the survey.

Addresses: `0x473df0`, `0x473e1c`, `0x473e30`, `0x473e8c`, `0x473ef5`, `0x473ef9`, `0x46bc20`, `0x46bc72`, `0x46bc80`, `0x46bc9d`, `0x46bc33`, `0x46ddd0`, `0xb42199`, `0xb421e8`
Confidence: verified
Proof: one
Test: none

`0x473df0` sends only when `0xb421f0` is set and the word `0xb421f4` is nonzero, tail-jumping to
`SendSurveyResult 0x5ab600` with the size in `ecx` and the data in `edx`. In the update,
`0x46bc20` tests the run-once flag `0xb42199`, `0x46bc72` sets it, `0x46bc80` takes a failed run to
`0x473e30`, and `0x46bc9d` opens the dialog; with the flag set, `0x46bc33` `cmp eax,0x5dc; seta`
ends the survey once more than 1,500 ms have passed since `0xb421e8`. `0x473e30` clears the
flag, frees the result and the file, creates the logon listener at `0xc28118`, which also holds the realm list, when there is none
(`0x473e8c`), calls its slot 4 with state 4, `LOGIN_STATE_AUTHENTICATED` and `LOGIN_OK`
(`0x473ef5`), and stores state 1 (`0x473ef9`). `0x46ddd0` calls `0x473df0` only when its read of
argument 1 with default 0 returns nonzero (`0x46ddd7`), and `0x473e30` always.
